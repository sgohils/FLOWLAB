"""The root ``.dockerignore`` must not break the images built from this repo.

Docker is not available on every machine that edits this repository, and a
``.dockerignore`` that quietly drops a path a Dockerfile COPYs does not fail
loudly: the image builds and is broken at runtime, or the build fails with a
missing-source error ten minutes later.  So the exclusion list is checked here
instead, against the two build contexts docker-compose.yml declares.

The matcher below mirrors Docker's: patterns are ``/``-separated, ``**`` spans
any number of segments, and the last matching pattern wins.
"""

from __future__ import annotations

import fnmatch
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
ROOT_IGNORE = REPO_ROOT / ".dockerignore"
FRONTEND_IGNORE = REPO_ROOT / "frontend" / ".dockerignore"


def _patterns(path: Path) -> list[tuple[list[str], bool]]:
    """``[([segments], is_negation)]`` for one ignore file."""
    result = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        negated = line.startswith("!")
        if negated:
            line = line[1:]
        line = line.rstrip("/")
        result.append((line.split("/"), negated))
    return result


def _match(segments: list[str], parts: list[str]) -> bool:
    if not segments:
        return not parts
    head, rest = segments[0], segments[1:]
    if head == "**":
        return any(_match(rest, parts[index:]) for index in range(len(parts) + 1))
    if not parts or not fnmatch.fnmatchcase(parts[0], head):
        return False
    return _match(rest, parts[1:])


def _ignored(relative: str, patterns: list[tuple[list[str], bool]]) -> bool:
    """Docker drops a file when it, or any parent directory, is excluded."""
    parts = relative.replace("\\", "/").split("/")
    ignored = False
    for index in range(len(parts)):
        prefix = parts[: index + 1]
        for segments, negated in patterns:
            if _match(segments, prefix):
                ignored = not negated
    return ignored


def _compose_contexts() -> dict[str, str]:
    compose = yaml.safe_load((REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    return {
        name: str(service["build"]["context"])
        for name, service in compose["services"].items()
    }


# ------------------------------------------------------- the backend image


#: Every source backend/Dockerfile copies, with the line that copies it.
BACKEND_SOURCES = [
    "frontend/package.json",
    "frontend/package-lock.json",
    "frontend/src/main.tsx",
    "frontend/index.html",
    "frontend/vite.config.ts",
    "frontend/tsconfig.json",
    "backend/requirements.txt",
    "backend/main.py",
    "backend/config.py",
    "backend/demo/sample_analysis.json",
    "README.md",
]


def test_the_ignore_file_is_at_the_context_root():
    """Docker reads <context root>/.dockerignore and nothing else."""
    assert ROOT_IGNORE.is_file(), "a backend/.dockerignore is inert with `context: .`"
    assert _compose_contexts()["backend"] == "."


@pytest.mark.parametrize("relative", BACKEND_SOURCES)
def test_a_path_the_backend_image_copies_is_not_excluded(relative):
    assert (REPO_ROOT / relative).is_file(), f"{relative} does not exist in the repository"
    assert not _ignored(relative, _patterns(ROOT_IGNORE)), f"{relative} would leave the context"


@pytest.mark.parametrize(
    "relative",
    [
        ".venv",
        ".venv/Scripts/python.exe",
        "node_modules",
        "frontend/node_modules",
        "data",
        "data/uploads/clip.mp4",
        "data/flowlab.db",
        ".git",
        ".git/config",
        ".gitignore",
        "yolo11n.pt",
        "models/yolo11n.pt",
        "frontend/dist",
        "frontend/dist/index.html",
        "frontend/.vite",
        "backend/__pycache__",
        "backend/storage/__pycache__",
        "backend/main.pyc",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".coverage",
        "htmlcov",
        "flowlab.egg-info",
        ".github",
        "docs",
        "run.sh",
        "run.bat",
        "pyproject.toml",
        "backend/tests/test_api.py",
        "backend/scripts/doctor.py",
        "backend/validation/README.md",
    ],
)
def test_local_state_is_excluded(relative):
    assert _ignored(relative, _patterns(ROOT_IGNORE)), f"{relative} would ship in the context"


def test_the_exception_that_keeps_readme_is_not_dead_weight():
    """The exception is what a future `*.md` rule has to stay behind."""
    patterns = _patterns(ROOT_IGNORE)
    assert patterns[-1][1] is True, "the `!README.md` line must come last"
    assert not _ignored("README.md", patterns)


# ------------------------------------------------------- the frontend image


def test_the_dev_image_uses_its_own_context_root_ignore_file():
    """The root file cannot leak into a context whose root is ./frontend."""
    contexts = _compose_contexts()
    assert contexts["frontend"] == "./frontend"
    assert FRONTEND_IGNORE.is_file()
    patterns = _patterns(FRONTEND_IGNORE)
    assert _ignored("node_modules", patterns)
    # The dev Dockerfile only COPYs package.json/package-lock.json; src and
    # index.html are bind-mounted, so shipping them only masks a broken mount.
    assert not _ignored("package.json", patterns)
    assert not _ignored("package-lock.json", patterns)
    assert _ignored("src/main.tsx", patterns)
    assert _ignored("index.html", patterns)


def test_the_ignore_file_uses_no_absolute_or_parent_paths():
    for raw in ROOT_IGNORE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        assert not line.startswith("/"), f"{line} is context-absolute"
        assert ".." not in Path(line.lstrip("!")).parts, f"{line} escapes the context"
