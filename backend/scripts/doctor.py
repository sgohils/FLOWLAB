"""Environment diagnostics.

Run this before a demo.  It answers the three questions that actually go wrong:
are the Python packages importable, can the video pipeline read a file, and is
the model available locally?

    python -m backend.scripts.doctor
"""

from __future__ import annotations

import platform
import sys
from dataclasses import dataclass

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


def check_model(settings) -> Check:
    """Is the detector checkpoint present locally?"""
    from pathlib import Path

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


def check_storage(settings) -> Check:
    from backend.config import ensure_directories

    try:
        ensure_directories(settings)
        probe = settings.data_dir / ".doctor-write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        free = shutil_free_mb(settings.data_dir)
        return Check("data folder", True, f"{settings.data_dir} writable, {free} MB free")
    except Exception as exc:
        return Check("data folder", False, f"{settings.data_dir} not writable ({exc})")


def shutil_free_mb(path) -> int:
    import shutil

    return shutil.disk_usage(str(path)).free // (1024 * 1024)


def check_video_stack() -> Check:
    try:
        import numpy as np
        import cv2

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
    print(f"  repository {settings.data_dir}")
    print()

    checks = [
        *check_packages(),
        check_video_stack(),
        check_model(settings),
        check_storage(settings),
        check_database(),
    ]
    width = max(len(check.name) for check in checks)
    for check in checks:
        mark = "ok  " if check.ok else "FAIL"
        print(f"  [{mark}] {check.name:<{width}}  {check.detail}")

    failures = [check for check in checks if not check.ok and check.name in RUNTIME_REQUIRED]
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
