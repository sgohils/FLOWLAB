"""The encoding gate itself: what it detects, and that it looks at all.

The gate shipped a false all-clear twice, and both faults are in the *checker*
rather than in the code it checks:

* a source file carried U+FFFD REPLACEMENT CHARACTER while the signature list
  held the cp1252 misread of that character's UTF-8 bytes - a different string
  from a different accident - so the real thing was never looked for;
* the roots were relative to the current directory, so from anywhere but the
  repository root the scan found nothing, printed "clean" and exited 0.  It is
  wired into pre-commit, ``run.bat lint``, ``run.sh lint`` and CI: a green gate
  that had proved nothing.

Every fixture here is written to a temporary directory.  A fixture file in the
repository would be a file the gate has to be trusted not to report, and a test
that depends on that trust is not a test.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

from backend.scripts import check_encoding
from backend.scripts.check_encoding import REPO_ROOT, ROOTS, SIGNATURES, main

#: The three damage forms the check exists for, written as escapes so this file
#: stays pure ASCII and cannot report itself.
REPLACEMENT = "\ufffd"
MOJIBAKE_DASH = "\u00e2\u20ac\u0094"  # an em dash decoded as cp1252
MISREAD_REPLACEMENT = "\u00ef\u00bf\u00bd"  # U+FFFD's UTF-8 bytes decoded as cp1252

SCANNED = re.compile(r"scanned (\d+) files")


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run the gate as the pre-commit hook and CI do: as a module, in a subprocess."""
    return subprocess.run(
        [sys.executable, "-m", "backend.scripts.check_encoding", *args],
        cwd=str(cwd),
        env={
            **os.environ,
            "PYTHONPATH": str(REPO_ROOT),
            # Decoding here must not depend on the console code page either.
            "PYTHONIOENCODING": "utf-8",
        },
        capture_output=True,
        text=True,
        timeout=180,
    )


def _write(directory: Path, name: str, text: str) -> Path:
    path = directory / name
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


# ------------------------------------------------------------ what is detected


def test_a_genuine_replacement_character_is_detected(tmp_path):
    """The character a lossy editor substitutes, which the old signature missed."""
    path = _write(tmp_path, "panel.tsx", f"const label = '1280 x 720 {REPLACEMENT}';\n")
    problems, scanned = check_encoding.find_problems([tmp_path])
    assert scanned == 1
    assert [problem for problem in problems if "U+FFFD" in problem], problems
    # The report is actionable: which signature, which file, which line.
    hit = next(problem for problem in problems if "U+FFFD" in problem)
    assert str(path) in hit
    assert hit.endswith(":1")
    assert REPLACEMENT not in hit, "the signature must be printed escaped, not literally"


def test_the_replacement_character_and_its_cp1252_misread_are_two_signatures():
    """The old bug in one assertion: the list named one and matched the other."""
    assert REPLACEMENT in SIGNATURES
    assert MISREAD_REPLACEMENT in SIGNATURES, "cp1252 mojibake detection must not regress"
    assert REPLACEMENT != MISREAD_REPLACEMENT


def test_cp1252_mojibake_is_still_detected(tmp_path):
    """The damage this repository actually suffered, and the reason the gate exists."""
    path = _write(tmp_path, "report.md", f"The frame is 1280 x 720{MOJIBAKE_DASH} 24 fps.\n")
    problems, scanned = check_encoding.find_problems([tmp_path])
    assert scanned == 1
    assert [problem for problem in problems if "em dash" in problem], problems
    assert str(path) in problems[0]


def test_a_clean_file_is_not_flagged(tmp_path):
    """Correct non-ASCII is not damage: the gate must not drive authors to ASCII."""
    _write(
        tmp_path,
        "notes.md",
        "1280 x 720 \u2014 24 fps, 30 vehicles \u00b7 caf\u00e9 au lait \u2026\n",
    )
    problems, scanned = check_encoding.find_problems([tmp_path])
    assert scanned == 1
    assert problems == []


def test_a_bom_and_invalid_utf8_are_still_reported(tmp_path):
    """The pre-existing checks, kept: a BOM and an undecodable byte are both damage."""
    (tmp_path / "bom.py").write_bytes(b"\xef\xbb\xbfprint('hi')\n")
    (tmp_path / "latin.py").write_bytes(b"print('caf\xe9')\n")
    problems, scanned = check_encoding.find_problems([tmp_path])
    assert scanned == 2
    assert [problem for problem in problems if "byte-order mark" in problem], problems
    assert [problem for problem in problems if "not utf-8" in problem], problems


# ------------------------------------------------------------- the exit status


def test_the_exit_code_is_nonzero_on_a_hit_and_zero_when_clean(tmp_path):
    _write(tmp_path, "panel.tsx", "const label = '1280 x 720';\n")
    clean = _run(str(tmp_path), cwd=REPO_ROOT)
    assert clean.returncode == 0, clean.stdout + clean.stderr
    assert clean.stdout.strip() == "scanned 1 files: clean"

    _write(tmp_path, "panel.tsx", f"const label = '{REPLACEMENT}';\n")
    dirty = _run(str(tmp_path), cwd=REPO_ROOT)
    assert dirty.returncode == 1, dirty.stdout + dirty.stderr
    assert "panel.tsx" in dirty.stdout
    assert "1 problem(s)" in dirty.stdout

    _write(tmp_path, "panel.tsx", "const label = '1280 x 720';\n")
    assert _run(str(tmp_path), cwd=REPO_ROOT).returncode == 0


def test_scanning_nothing_is_an_error_rather_than_a_pass(tmp_path, capsys):
    """The gate that proved nothing must not report success."""
    assert main([str(tmp_path / "does-not-exist")]) == 2
    assert "no source files" in capsys.readouterr().out
    (tmp_path / "empty").mkdir()
    assert main([str(tmp_path / "empty")]) == 2


# ---------------------------------------------- independent of the working dir


def test_the_roots_are_anchored_to_the_repository_not_the_working_directory():
    assert all(root.is_absolute() for root in ROOTS)
    assert all(root.is_dir() for root in ROOTS), ROOTS
    assert all(root.is_relative_to(REPO_ROOT) for root in ROOTS)
    assert Path(check_encoding.__file__).resolve().parents[2] == REPO_ROOT


def test_the_same_files_are_scanned_from_any_working_directory(tmp_path):
    """The pre-commit hook, CI and `run.bat lint` all start somewhere else."""
    from_root = _run(cwd=REPO_ROOT)
    from_elsewhere = _run(cwd=tmp_path)
    assert from_root.returncode == from_elsewhere.returncode
    assert SCANNED.search(from_root.stdout).group(1) == SCANNED.search(
        from_elsewhere.stdout
    ).group(1)
    assert from_root.stdout == from_elsewhere.stdout.replace(str(REPO_ROOT) + "\\", "")
    assert int(SCANNED.search(from_root.stdout).group(1)) > 50


# ------------------------------------------- the guard that would have caught it


def test_no_source_file_in_the_repository_contains_a_replacement_character():
    """The assertion the shipped defect needed, over exactly the gate's own roots."""
    offenders = []
    for root in ROOTS:
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix not in check_encoding.SUFFIXES:
                continue
            if REPLACEMENT in path.read_bytes().decode("utf-8-sig", errors="replace"):
                offenders.append(f"{path.relative_to(REPO_ROOT)}")
    assert not offenders, f"U+FFFD in the sources: {offenders}"
