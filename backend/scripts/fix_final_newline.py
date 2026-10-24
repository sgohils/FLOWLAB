r"""Terminate every text file with exactly one newline, in its own convention.

A repository-local replacement for pre-commit-hooks' `end-of-file-fixer`, and it
exists for one reason: the upstream hook is line-ending blind.

Upstream appends a hard-coded ``b"\n"`` to a file that does not end in a line
break.  In a working tree that is CRLF - which is what ``core.autocrlf=true`` on
Windows produces - that turns

    ...last line\r\n

into

    ...last line\r\n\n

a file that is CRLF everywhere and LF on its own last line.  Git then hides the
difference: autocrlf normalises CRLF to LF on the next `git add`, so the wrong
byte is visible in the working tree and invisible in the commit.  Renormalising
the file instead would rewrite all ~5700 lines of
backend/demo/sample_reference.json, and one wrong byte is a far smaller problem
than a diff nobody can review.

So the terminator added is the one the file already uses.  The rest of the
contract is deliberately identical to upstream's - extra trailing blank lines
collapse to a single terminator, a file that is nothing but line breaks becomes
empty, and binary files are left alone - so turning this hook on is not a
behaviour change for any file that is already correct.

    python -m backend.scripts.fix_final_newline path/to/file ...
"""

from __future__ import annotations

import sys
from pathlib import Path

#: How many bytes count as "this file is binary".
_SNIFF_BYTES = 8192


def dominant_newline(data: bytes) -> bytes:
    """The line terminator ``data`` is already written with.

    CRLF wins if the file contains even one CRLF: that is the reading which
    cannot make a mixed file more mixed.  A file with no line break at all is
    reported as LF, because a single-line file is no evidence either way and the
    convention this repository declares is LF (.editorconfig).
    """
    return b"\r\n" if b"\r\n" in data else b"\n"


def fix_bytes(data: bytes) -> bytes:
    """``data`` trimmed to exactly one, convention-matching final newline."""
    body = data.rstrip(b"\r\n")
    if not body:
        # Upstream truncates a file made only of line breaks to empty rather
        # than leaving a lone newline behind.  Same rule, same reason.
        return b""
    return body + dominant_newline(data)


def fix_file(path: Path) -> bool:
    """Rewrite ``path`` in place if it needs it.  True when it changed."""
    data = path.read_bytes()
    if b"\x00" in data[:_SNIFF_BYTES]:
        # Binary.  pre-commit's `types: [text]` keeps these away already, but a
        # NUL byte is the one signal certain enough to act on regardless.
        return False
    fixed = fix_bytes(data)
    if fixed == data:
        return False
    path.write_bytes(fixed)
    return True


def main(argv: list[str] | None = None) -> int:
    """Fix every path given, or every path in ``argv``.  1 when anything changed."""
    paths = sys.argv[1:] if argv is None else argv
    changed = False
    for name in paths:
        try:
            if fix_file(Path(name)):
                print(f"Fixing {name}")
                changed = True
        except OSError as exc:
            print(f"{name}: {exc}", file=sys.stderr)
            return 1
    return 1 if changed else 0


if __name__ == "__main__":
    raise SystemExit(main())
