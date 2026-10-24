"""The doctor has to be able to fail.

``doctor.py`` used to print "ok" for every package it could import, whatever
version that was, which is how OpenCV 5.x ran for a while behind a ``<5`` pin.
These tests pin the comparison and, just as importantly, pin the declared
bounds against the environment the suite is actually running in.
"""

from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path

import pytest

from backend.scripts import doctor

REPO_ROOT = Path(__file__).resolve().parents[2]


# ------------------------------------------------------------- the comparison


@pytest.mark.parametrize(
    ("version", "bound", "expected"),
    [
        ("5.0.0.93", ">=4.10,<6", True),
        ("5.0.0.93", ">=4.10,<5", False),  # the stale bound that shipped
        ("4.10.0.84", ">=4.10,<5", True),
        ("4.9.0", ">=4.10,<6", False),
        ("6.0.0", ">=4.10,<6", False),
        ("4.10", ">=4.10,<6", True),  # a short version pads with zeros
        ("4.10.0", ">=4.10,<6", True),
        ("5.0.0rc1", ">=4.10,<6", False),  # a pre-release is not ">= 4.10"
        ("5.0.0", ">=4.10", True),
        ("5.0.0", "", True),  # no bound declared, nothing to violate
        ("5.0.0", "banana", False),  # an unreadable bound must not pass
        ("5.0.0", "==5.0.0", True),
        ("5.0.1", "==5.0.0", False),
        ("5.0.0", "!=5.0.0", False),
    ],
)
def test_satisfies(version: str, bound: str, expected: bool):
    assert doctor.satisfies(version, bound) is expected


def test_the_declared_bounds_are_parsed_from_the_file():
    declared = doctor.declared_requirements()
    assert declared["opencv-python"] == ">=4.10,<6"
    assert declared["uvicorn"] == ">=0.34,<1", "an extras marker must not hide the bound"
    assert "pytest" not in declared, "dev-only packages are not runtime bounds"


# -------------------------------------------------------------- the check runs


def test_the_pin_check_passes_against_this_interpreter():
    """The environment CI installs must satisfy the bounds the repo declares."""
    check = doctor.check_dependency_pins()
    assert check.ok, check.detail


def test_the_pin_check_fails_when_a_bound_is_stale(monkeypatch):
    """A doctor that cannot fail is not a doctor."""
    monkeypatch.setattr(
        doctor, "declared_requirements", lambda: {"opencv-python": ">=4.10,<5"}
    )

    check = doctor.check_dependency_pins()

    assert not check.ok
    assert "violates" in check.detail
    assert check.name in doctor.BLOCKING


def test_an_uninstalled_package_is_a_pin_failure(monkeypatch):
    monkeypatch.setattr(
        doctor, "declared_requirements", lambda: {"definitely-not-installed": ">=1"}
    )

    check = doctor.check_dependency_pins()

    assert not check.ok
    assert "not installed" in check.detail


def test_a_missing_requirements_file_is_a_pin_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(doctor, "REQUIREMENTS_FILE", tmp_path / "nope.txt")

    check = doctor.check_dependency_pins()

    assert not check.ok
    assert "cannot read" in check.detail


# ------------------------------------------------------------------- no drift


def test_requirements_txt_and_pyproject_declare_the_same_bounds():
    """The two files are copies by design; a copy that drifts is a lie."""
    runtime = [
        line.split("#", 1)[0].strip()
        for line in doctor.REQUIREMENTS_FILE.read_text(encoding="utf-8").splitlines()
    ]
    runtime = [line for line in runtime if line]

    declared = tomllib.loads(
        (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]["dependencies"]

    assert sorted(runtime) == sorted(declared)


def test_requirements_dev_txt_and_pyproject_dev_extra_agree():
    """Same rule for the dev list, and the reason pre-commit is on it.

    `pre-commit install` is the first instruction in CONTRIBUTING.md, so
    `pre-commit` has to be a declared dev dependency.  It was missing from both
    copies, which is the one way this drift test can fail: both files agreed
    with each other and neither agreed with the instructions.
    """
    dev_file = [
        line.split("#", 1)[0].strip()
        for line in (REPO_ROOT / "backend" / "requirements-dev.txt")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    dev_file = [line for line in dev_file if line]

    declared = tomllib.loads(
        (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]["optional-dependencies"]["dev"]

    assert sorted(dev_file) == sorted(declared)
    assert any(line.startswith("pre-commit") for line in dev_file)


def test_the_project_urls_point_at_the_configured_remote():
    """A 404 in [project.urls] is worse than no URL at all.

    They were written as github.com/SG-925/FLOWLAB while `git remote -v` says
    github.com/sgohils/FLOWLAB.  SG-925 is the commit author (LICENSE,
    [project].authors); it is not the account the code is hosted under, and the
    two being different is exactly how the wrong URL survived review.
    """
    urls = tomllib.loads(
        (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )["project"].get("urls", {})

    remote = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    origin = remote.removesuffix(".git").removesuffix("/")

    assert origin.endswith("/FLOWLAB"), f"unexpected remote: {remote}"
    assert set(urls.values()) == {origin}, f"declared URLs disagree with {remote}"
