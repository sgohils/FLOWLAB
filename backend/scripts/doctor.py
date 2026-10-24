"""Environment diagnostics.

Run this before a demo.  It answers the three questions that actually go wrong:
are the Python packages importable, can the video pipeline read a file, and is
the model available locally?

    python -m backend.scripts.doctor
"""

from __future__ import annotations

import os
import platform
import re
import sys
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as installed_version
from pathlib import Path

from backend.config import BACKEND_DIR, PROJECT_DIR, Settings

#: (import name, why FLOWLAB needs it)
REQUIRED: tuple[tuple[str, str], ...] = (
    ("fastapi", "HTTP API"),
    ("uvicorn", "server"),
    ("pydantic", "data validation"),
    ("numpy", "arrays"),
    ("cv2", "video decode and annotation"),
    ("ultralytics", "detector"),
    ("torch", "detector runtime"),
    ("pytest", "test suite (optional at runtime)"),
)

RUNTIME_REQUIRED = {"fastapi", "uvicorn", "pydantic", "numpy", "cv2", "ultralytics", "torch"}

#: The bounds this repository declares.  They are read from the file rather
#: than repeated here: a doctor that carries its own copy of the numbers can
#: agree with the checkout while disagreeing with what it is checking, which is
#: the failure mode this function exists to catch.
REQUIREMENTS_FILE = BACKEND_DIR / "requirements.txt"

#: Distribution name -> module name, where the two differ.
IMPORT_NAMES = {"opencv-python": "cv2"}

#: Checks that must pass before FLOWLAB can run.
BLOCKING = set(RUNTIME_REQUIRED) | {"dependency pins"}

#: Name of the storage check.  The header prints the same directory as
#: "data dir", and one term for one thing is the whole point of a report.
DATA_DIR_CHECK = "data dir"

#: The install command to quote back to the operator.  run.bat and run.sh both
#: exist and this is the one that runs here; quoting ./run.sh to a Windows user
#: is a dead end.
INSTALL_COMMAND = "run.bat install" if os.name == "nt" else "./run.sh install"


@dataclass(slots=True)
class Check:
    name: str
    ok: bool
    detail: str


def check_packages() -> list[Check]:
    results: list[Check] = []
    for name, purpose in REQUIRED:
        try:
            module = __import__(name)
            version = getattr(module, "__version__", "unknown")
            optional = "" if name in RUNTIME_REQUIRED else "  (dev only)"
            results.append(Check(name, True, f"{version} — {purpose}{optional}"))
        except Exception as exc:  # ImportError, but a broken install can raise more
            results.append(Check(name, False, f"missing ({type(exc).__name__})"))
    return results


# ------------------------------------------------------------ version pins

#: One clause of a bound, e.g. ``>=4.10`` or ``<6``.
_CLAUSE = re.compile(r"^(==|>=|<=|!=|>|<)?\s*([0-9][\w.+-]*)$")
_REQUIREMENT = re.compile(r"^([A-Za-z0-9._-]+)\s*(?:\[[^\]]*\])?\s*([<>=!~].*)?$")


def declared_requirements(path: Path | None = None) -> dict[str, str]:
    """``{distribution: bound}`` as written in ``backend/requirements.txt``.

    The path is looked up at call time rather than bound as a default, so the
    module attribute stays the single place the file is named.
    """
    declared: dict[str, str] = {}
    for line in (path or REQUIREMENTS_FILE).read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or line.startswith(("-", "#")):
            continue
        match = _REQUIREMENT.match(line)
        if match is None:
            continue
        declared[match.group(1)] = (match.group(2) or "").strip()
    return declared


def _release(version: str) -> tuple[tuple[int, ...], bool]:
    """``(release segments, is_prerelease)`` for a PEP 440 version string."""
    head = re.split(r"[-+]", version.strip(), maxsplit=1)[0]
    segments = tuple(int(part) for part in re.findall(r"\d+", head))
    return (segments or (0,)), bool(re.search(r"[A-Za-z]", version))


def _compare(left: tuple[int, ...], right: tuple[int, ...]) -> int:
    """Compare releases, padding the short one: 4.10 and 4.10.0 are equal."""
    width = max(len(left), len(right))
    padded_left = left + (0,) * (width - len(left))
    padded_right = right + (0,) * (width - len(right))
    return (padded_left > padded_right) - (padded_left < padded_right)


def satisfies(version: str, bound: str) -> bool:
    """Does ``version`` satisfy a comma-separated bound such as ``>=4.10,<6``?

    A clause this cannot parse is a failure, not a pass: a doctor that cannot
    fail is not a doctor.  Pre-releases (``5.0.0rc1``) do not satisfy a bound
    that does not name one, which matches how pip treats a plain lower bound.
    """
    for clause in bound.split(","):
        clause = clause.strip()
        if not clause:
            continue
        match = _CLAUSE.match(clause)
        if match is None:
            return False
        operator = match.group(1) or "=="
        wanted, wanted_pre = _release(match.group(2))
        found, found_pre = _release(version)
        if found_pre and not wanted_pre:
            return False
        order = _compare(found, wanted)
        if operator == ">=" and order < 0:
            return False
        if operator == ">" and order <= 0:
            return False
        if operator == "<=" and order > 0:
            return False
        if operator == "<" and order >= 0:
            return False
        if operator == "==" and order != 0:
            return False
        if operator == "!=" and order == 0:
            return False
    return True


def check_dependency_pins() -> Check:
    """Does every installed runtime package match the version we declare?

    This is the check that notices a stale bound.  It used to report "ok" no
    matter what was installed, which is how OpenCV 5.x survived a `<5` pin.
    """
    try:
        declared = declared_requirements()
    except OSError as exc:
        return Check("dependency pins", False, f"cannot read {REQUIREMENTS_FILE.name} ({exc})")
    if not declared:
        return Check("dependency pins", False, f"no bounds declared in {REQUIREMENTS_FILE.name}")

    problems: list[str] = []
    for name, bound in declared.items():
        try:
            found = installed_version(name)
        except PackageNotFoundError:
            problems.append(f"{IMPORT_NAMES.get(name, name)} not installed")
            continue
        if not satisfies(found, bound):
            problems.append(f"{name} {found} violates '{bound}'")
    if problems:
        return Check(
            "dependency pins",
            False,
            f"{'; '.join(problems)} - run {INSTALL_COMMAND}",
        )
    return Check(
        "dependency pins",
        True,
        f"{len(declared)} packages match {REQUIREMENTS_FILE.name}",
    )


def check_model(settings: Settings) -> Check:
    """Is the detector checkpoint present locally?"""
    name = settings.model_name
    if Path(name).is_file():
        size_mb = Path(name).stat().st_size / 1e6
        return Check("model weights", True, f"{name} present ({size_mb:.1f} MB)")
    cached = Path(settings.data_dir).parent / name
    if cached.is_file():
        return Check("model weights", True, f"{cached} present")
    return Check(
        "model weights",
        False,
        f"{name} not found — the first analysis downloads it from the Ultralytics "
        "release server (needs internet once)",
    )


def check_storage(settings: Settings) -> Check:
    from backend.config import ensure_directories

    try:
        ensure_directories(settings)
        probe = settings.data_dir / ".doctor-write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        free = shutil_free_mb(settings.data_dir)
        return Check(DATA_DIR_CHECK, True, f"{settings.data_dir} writable, {free} MB free")
    except Exception as exc:
        return Check(DATA_DIR_CHECK, False, f"{settings.data_dir} not writable ({exc})")


def shutil_free_mb(path: Path) -> int:
    import shutil

    return shutil.disk_usage(str(path)).free // (1024 * 1024)


def check_video_stack() -> Check:
    try:
        import cv2
        import numpy as np

        frame = np.zeros((32, 32, 3), dtype=np.uint8)
        ok, _ = cv2.imencode(".png", frame)
        return Check("opencv", bool(ok), f"version {cv2.__version__}, encode/decode ok")
    except Exception as exc:
        return Check("opencv", False, f"broken: {exc}")


def check_database() -> Check:
    try:
        from backend.api.state import database

        database.list_recent(limit=1)
        return Check("database", True, "readable")
    except Exception as exc:
        return Check("database", False, f"unavailable: {exc}")


def main() -> int:
    from backend.config import settings

    print("FLOWLAB doctor")
    print(f"  python     {sys.version.split()[0]} on {platform.system()} {platform.machine()}")
    # These are two different paths and the old report printed one under the
    # other name: settings.data_dir is the writable data directory
    # (FLOWLAB_DATA_DIR, ./data by default), which is where uploads, annotated
    # videos, flowlab.db and the downloaded checkpoint live.  Neither of them is
    # the repository, so name both.
    print(f"  repository {PROJECT_DIR}")
    print(f"  data dir   {settings.data_dir}")
    print()

    checks = [
        *check_packages(),
        check_video_stack(),
        check_dependency_pins(),
        check_model(settings),
        check_storage(settings),
        check_database(),
    ]
    width = max(len(check.name) for check in checks)
    for check in checks:
        mark = "ok  " if check.ok else "FAIL"
        print(f"  [{mark}] {check.name:<{width}}  {check.detail}")

    failures = [check for check in checks if not check.ok and check.name in BLOCKING]
    print()
    if failures:
        print(f"{len(failures)} blocking problem(s). Fix these before running FLOWLAB:")
        for check in failures:
            print(f"  - {check.name}: pip install -r backend/requirements.txt")
        return 1
    print("All runtime dependencies are present.")
    if not check_model(settings).ok:
        print(
            "  Note: the model weights are not on disk yet. The first analysis will "
            "download them, which needs internet access once."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
