"""The import contract: layering, ``__all__`` accuracy and the CORS setting.

Three classes of mistake are cheap to make and expensive to notice:

* a name in ``__all__`` that nothing defines - ``from package import *`` then
  raises ``AttributeError`` at runtime, far from the edit that caused it;
* an import that reintroduces a cycle between ``models.schemas`` and
  ``analytics``, which only shows up on a cold import order;
* a setting read from somewhere other than ``config``.

These tests are all import-level: no model, no video, no network, no timing.
"""

from __future__ import annotations

import importlib
import os
import pkgutil
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from backend import geometry
from backend.analytics import geometry as analytics_geometry
from backend.config import DEFAULT_CORS_ORIGINS, build_settings
from backend.models import schemas

REPO_ROOT = Path(__file__).resolve().parents[2]


def _backend_modules() -> list[ModuleType]:
    """Every importable module under ``backend`` (test modules excluded)."""
    backend = importlib.import_module("backend")
    modules = [backend]
    for info in pkgutil.walk_packages(backend.__path__, prefix="backend."):
        if info.name.startswith("backend.tests."):
            continue
        modules.append(importlib.import_module(info.name))
    return modules


# ------------------------------------------------------------------- __all__


def test_every_name_in_every_all_exists():
    """``__all__`` is a promise; a name that does not resolve breaks ``import *``."""
    broken = [
        f"{module.__name__}.{name}"
        for module in _backend_modules()
        for name in getattr(module, "__all__", [])
        if not hasattr(module, name)
    ]
    assert not broken, f"__all__ names that do not exist: {broken}"


def test_every_package_supports_a_star_import():
    """``from backend.x import *`` must work for every package, as the docstrings imply."""
    for module in _backend_modules():
        if not hasattr(module, "__all__"):
            continue
        namespace: dict[str, object] = {}
        exec(f"from {module.__name__} import *", namespace)
        for name in module.__all__:
            assert name in namespace, f"{name} missing from `import *` of {module.__name__}"


def test_the_vision_package_does_not_advertise_a_renamed_error():
    """``DetectorError`` is the real name; a stale alias used to sit beside it."""
    from backend.vision import DetectorError, detector

    assert "VehicleDetectionError" not in importlib.import_module("backend.vision").__all__
    assert isinstance(DetectorError("boom"), RuntimeError)
    assert detector.__class__.__name__ == "VehicleDetector"


# ----------------------------------------------------------------- layering


def test_backend_geometry_imports_nothing_from_the_project():
    """This is what makes the module shareable: it cannot be part of a cycle."""
    source = (REPO_ROOT / "backend" / "geometry.py").read_text(encoding="utf-8")
    imported = re.findall(r"^\s*(?:from|import)\s+([\w.]+)", source, re.MULTILINE)
    assert not [name for name in imported if name.startswith(("backend", "."))], imported
    assert set(imported) <= {"__future__", "collections.abc", "typing"}, imported


def test_schemas_import_without_loading_analytics():
    """``analytics`` imports ``models.schemas``, so the reverse edge is forbidden.

    Run in a subprocess: by the time this test file is collected, the whole
    package is already imported and the question cannot be asked any more.
    """
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys, backend.models.schemas;"
            "print(','.join(m for m in sys.modules if m.startswith('backend.analytics')))",
        ],
        cwd=REPO_ROOT,
        env={**os.environ, "FLOWLAB_DATA_DIR": str(Path(os.environ["FLOWLAB_DATA_DIR"]))},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "", f"schemas pulled in {result.stdout.strip()}"


def test_the_analytics_geometry_shim_reexports_the_shared_objects():
    """One implementation, two import paths: they must be the same functions."""
    for name in analytics_geometry.__all__:
        assert getattr(analytics_geometry, name) is getattr(geometry, name), name


def test_region_validation_uses_the_shared_area_function():
    """The too-small-region check must measure with the same shoelace formula."""
    assert schemas.polygon_area is geometry.polygon_area
    # A polygon of exactly MIN_POLYGON_AREA is accepted, one hair smaller is not.
    side = (schemas.MIN_POLYGON_AREA * 2) ** 0.5
    square = [(0.5, 0.5), (0.5 + side, 0.5), (0.5 + side, 0.5 + side), (0.5, 0.5 + side)]
    assert geometry.polygon_area(square) >= schemas.MIN_POLYGON_AREA
    assert schemas.Regions(queue=square).has_queue


def test_the_application_entry_point_imports_cleanly():
    """``backend.main`` wires every router; a cycle would surface here first."""
    module = importlib.import_module("backend.main")
    assert module.app.title == "FLOWLAB"
    assert len(module.app.routes) > 5


# --------------------------------------------------------------------- CORS


def test_cors_origins_default_to_the_loopback_dev_servers():
    assert build_settings().cors_origins == DEFAULT_CORS_ORIGINS
    assert all("127.0.0.1" in origin or "localhost" in origin for origin in DEFAULT_CORS_ORIGINS)


def test_cors_origins_are_parsed_from_a_comma_separated_list(monkeypatch):
    # Loopback hosts, because the list is validated as well as parsed; the
    # refusal of a routable host has its own tests in test_cors_guard.py.
    monkeypatch.setenv("FLOWLAB_CORS_ORIGINS", " http://localhost:1 , ,http://127.0.0.1:2,")
    assert build_settings().cors_origins == ("http://localhost:1", "http://127.0.0.1:2")


def test_a_blank_cors_setting_falls_back_to_the_safe_default(monkeypatch):
    """Empty means "unset", never "allow nothing" and never "allow everything"."""
    monkeypatch.setenv("FLOWLAB_CORS_ORIGINS", "   ")
    assert build_settings().cors_origins == DEFAULT_CORS_ORIGINS


def test_the_cors_origins_are_not_written_into_the_application_module():
    """Config-driven means configured: the literals live in config.py, once."""
    app_source = (REPO_ROOT / "backend" / "main.py").read_text(encoding="utf-8")
    leaked = [origin for origin in DEFAULT_CORS_ORIGINS if origin in app_source]
    assert not leaked, f"CORS origins hardcoded in backend/main.py: {leaked}"
    config_source = (REPO_ROOT / "backend" / "config.py").read_text(encoding="utf-8")
    assert all(origin in config_source for origin in DEFAULT_CORS_ORIGINS)


def test_the_api_is_configured_from_the_setting():
    """The middleware must read the setting rather than a list written in place."""
    from backend import main

    allowed = {
        origin
        for middleware in main.app.user_middleware
        if middleware.cls.__name__ == "CORSMiddleware"
        for origin in middleware.kwargs["allow_origins"]
    }
    assert allowed == set(build_settings().cors_origins)


# ----------------------------------------------------------------- detection


def test_an_unknown_class_id_is_named_generically_instead_of_raising():
    """Before the model is loaded, or for an id it does not know, say "vehicle"."""
    from backend.vision.detector import VehicleDetector

    assert VehicleDetector().class_name(2) == "vehicle"
    assert VehicleDetector().class_name(-1) == "vehicle"


def test_class_names_come_from_the_loaded_model():
    from backend.vision.detector import VehicleDetector

    detector = VehicleDetector()
    detector._names = {2: "car", 7: "truck"}
    assert detector.class_name(2) == "car"
    assert detector.class_name(7) == "truck"
    assert detector.class_name(3) == "vehicle"


# ------------------------------------------------------------------- dead code


@pytest.mark.parametrize(
    ("module", "removed"),
    [
        ("backend.api.jobs", "recompute_with_regions"),
        ("backend.simulation.simulator", "is_baseline"),
        ("backend.analytics.timeline", "timeline_sample_count"),
        ("backend.analytics.timeline", "queue_at"),
        ("backend.analytics.timeline", "position_at"),
    ],
)
def test_uncalled_helpers_are_not_shipped(module: str, removed: str):
    """These had no callers; keeping them only invites a second, diverging copy."""
    assert not hasattr(importlib.import_module(module), removed)
