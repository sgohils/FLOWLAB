"""The final-newline hook must not change a file's line endings.

``backend/scripts/fix_final_newline.py`` replaces pre-commit-hooks'
``end-of-file-fixer`` because upstream appends a literal ``b"\\n"``.  In a CRLF
working tree - which is what ``core.autocrlf=true`` produces on Windows, and
this repository is developed on Windows - that leaves the last line of a file
terminated differently from every other line in it.  These tests pin the
behaviour that makes the replacement safe, and pin the byte the hook writes.
"""

from __future__ import annotations

import pytest

from backend.scripts import fix_final_newline as fixer


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        # The whole point: a CRLF file gets CRLF, never a lone LF.
        (b"a\r\nb", b"a\r\nb\r\n"),
        (b"a\r\nb\r\n", b"a\r\nb\r\n"),
        (b"a\nb", b"a\nb\n"),
        (b"a\nb\n", b"a\nb\n"),
        # A single-line file has no evidence of a convention; LF is the one this
        # repository declares in .editorconfig.
        (b"one line", b"one line\n"),
        # Extra trailing blank lines collapse to one terminator, as upstream does.
        (b"a\n\n\n", b"a\n"),
        (b"a\r\n\r\n\r\n", b"a\r\n"),
        # A file that is nothing but line breaks becomes empty, again as upstream.
        (b"\n", b""),
        (b"\r\n\r\n", b""),
        (b"", b""),
        # Already-correct input is returned unchanged, byte for byte.
        (b"a\nb\n", b"a\nb\n"),
        (b"a\r\nb\r\n", b"a\r\nb\r\n"),
    ],
)
def test_fix_bytes(data: bytes, expected: bytes):
    assert fixer.fix_bytes(data) == expected


def test_a_mixed_file_is_not_made_more_mixed():
    """One stray LF in a CRLF file must not flip the file to LF.

    This is the regression the replacement exists for, in the shape the worktree
    actually gets into: a CRLF file whose last line an editor wrote with LF.
    """
    once = fixer.fix_bytes(b"a\r\nb\r\n\n")
    assert once == b"a\r\nb\r\n"
    assert fixer.fix_bytes(once) == once, "fixing is idempotent"


def test_every_line_ending_survives_a_fix():
    """No byte inside the file may move: only the terminator is added."""
    body = b"x = 1\r\nif x:\r\n    pass"
    fixed = fixer.fix_bytes(body)
    assert fixed != body, "this input is the one that needs a terminator"
    assert fixed.count(b"\r\n") == body.count(b"\r\n") + 1
    assert fixed.count(b"\n") == body.count(b"\n") + 1
    assert fixed.replace(b"\r\n", b"") == body.replace(b"\r\n", b"")


def test_binary_files_are_left_alone(tmp_path):
    blob = tmp_path / "screenshot.png"
    blob.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00")

    assert not fixer.fix_file(blob)
    assert blob.read_bytes() == b"\x89PNG\r\n\x1a\n\x00\x00"


def test_fix_file_rewrites_a_crlf_file_and_says_so(tmp_path):
    target = tmp_path / "run.bat"
    target.write_bytes(b"@echo off\r\necho hi")

    assert fixer.fix_file(target) is True
    assert target.read_bytes() == b"@echo off\r\necho hi\r\n"
    assert fixer.fix_file(target) is False, "a second run must be a no-op"


def test_main_returns_one_when_it_changed_a_file_and_zero_when_it_did_not(tmp_path):
    """pre-commit reads the exit code, not the output: 1 means "files modified"."""
    target = tmp_path / "a.txt"
    target.write_bytes(b"x\n")

    assert fixer.main([str(target)]) == 0
    target.write_bytes(b"x")
    assert fixer.main([str(target)]) == 1
    assert target.read_bytes() == b"x\n"


def test_main_reports_an_unreadable_path_instead_of_crashing(tmp_path):
    assert fixer.main([str(tmp_path / "missing.txt")]) == 1


def test_the_hook_is_wired_into_the_pre_commit_config():
    """The config and the script are two halves of one gate; drift is a dead gate."""
    from pathlib import Path

    config = Path(__file__).resolve().parents[2] / ".pre-commit-config.yaml"
    text = config.read_text(encoding="utf-8")

    assert "backend.scripts.fix_final_newline" in text
    # The upstream hook must not be enabled as well: it would undo this one by
    # appending the bare LF the replacement exists to avoid.
    hook_block = text.split("- id: end-of-file-fixer", 1)[1]
    assert "entry: python -m backend.scripts.fix_final_newline" in hook_block
    assert "pre-commit/pre-commit-hooks" in text
    assert text.count("- id: end-of-file-fixer") == 1
