"""Guard against encoding damage in the sources.

Two different accidents motivate this check, and they need different
signatures:

1. Four files were once edited through a Windows PowerShell pipeline that read
   UTF-8 as ANSI and wrote it back, turning an em dash into three characters.
   The symptom is visible in the interface ("1280 x 720" with a broken glyph) and
   is easy to miss in a diff, so this check runs as part of the verification pass.
2. A file was edited by a tool that could not represent a character, which
   substituted U+FFFD REPLACEMENT CHARACTER for it.  U+FFFD is a *valid* code
   point, so the file still decodes as UTF-8 and every byte-level mojibake
   signature above stays silent: the list used to carry a signature *named*
   "replacement character" that actually held the cp1252 misread of U+FFFD's
   three UTF-8 bytes - a different string, from a different accident.  The real
   character was never looked for.

So every signature names the form it matches: the cp1252 misread of a character,
and U+FFFD itself.  They are built from code points so this file is pure ASCII
and can never report itself, and they are reported escaped so a match can be
printed on a console that cannot encode it - which is precisely the case for the
character that matters most here.

Usage::

    python -m backend.scripts.check_encoding [PATH ...]

With no arguments the source roots of *this* repository are scanned.  The roots
are resolved from ``__file__`` rather than from the working directory, because
this script is a gate that runs from wherever the operator happens to be: a
pre-commit hook, ``run.bat lint``, ``run.sh lint`` and the CI job.  Run from
anywhere but the repository root it used to find no root at all, scan nothing,
print "clean" and exit 0 - a green gate that had proved nothing - so zero
scanned files is now an error rather than a pass.
"""

from __future__ import annotations

import pathlib
import sys
from collections.abc import Iterable, Sequence

#: The repository, derived from this file rather than from the current
#: directory, so the scan covers the same tree whoever invokes it.
REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SELF_PATH = pathlib.Path(__file__).resolve()

#: Source roots, relative to :data:`REPO_ROOT`.
ROOT_NAMES = ("frontend/src", "backend", "docs")
ROOTS: tuple[pathlib.Path, ...] = tuple(REPO_ROOT / name for name in ROOT_NAMES)

SUFFIXES = {".ts", ".tsx", ".py", ".md", ".css", ".html", ".json"}


def _chars(*codepoints: int) -> str:
    return "".join(chr(codepoint) for codepoint in codepoints)


#: Strings that only appear in this repository when text was damaged on its way
#: to disk: either UTF-8 decoded as cp1252, or a lossy editor substituting
#: U+FFFD.  Each entry is a distinct string, so a file carrying both faults is
#: reported twice.
SIGNATURES: dict[str, str] = {
    _chars(0xE2, 0x20AC, 0x94): "em dash misread as cp1252",
    _chars(0xE2, 0x20AC, 0xB7): "middle dot misread as cp1252",
    _chars(0xE2, 0x20AC, 0xA6): "ellipsis misread as cp1252",
    _chars(0xC3, 0xA9): "accented letter misread as cp1252",
    _chars(0xC2, 0xA0): "non-breaking space misread as cp1252",
    _chars(0xEF, 0xBF, 0xBD): "replacement character misread as cp1252",
    _chars(0xFFFD): "U+FFFD replacement character",
}


def _label(signature: str) -> str:
    """Printable form of a signature: code points plus an escape, both ASCII.

    Printing the matched characters themselves would raise
    ``UnicodeEncodeError`` on the cp1252 console this script usually runs on -
    U+FFFD is exactly the code point such a console cannot encode - and would
    hide the very line that needs fixing.
    """
    points = " ".join(f"U+{ord(char):04X}" for char in signature)
    escaped = signature.encode("unicode_escape").decode("ascii")
    return f"{points} {escaped}"


def find_problems(
    roots: Iterable[pathlib.Path],
    skip: Iterable[pathlib.Path] = (),
) -> tuple[list[str], int]:
    """Scan ``roots`` (files or directories); return ``(problems, scanned)``.

    Each problem names the signature that matched plus the file and line, so a
    report is something an editor can act on without re-deriving what the check
    looks for.
    """
    skipped = {path.resolve() for path in skip}
    problems: list[str] = []
    scanned = 0
    for root in roots:
        paths = [root] if root.is_file() else sorted(root.rglob("*"))
        for path in paths:
            if not path.is_file() or path.suffix not in SUFFIXES:
                continue
            if path.resolve() in skipped:
                continue
            scanned += 1
            raw = path.read_bytes()
            if raw[:3] == b"\xef\xbb\xbf":
                problems.append(f"byte-order mark: {path}")
            try:
                text = raw.decode("utf-8-sig")
            except UnicodeDecodeError as error:
                problems.append(f"not utf-8 ({error.reason}): {path}")
                continue
            for signature, name in SIGNATURES.items():
                if signature not in text:
                    continue
                line = next(
                    (i + 1 for i, row in enumerate(text.splitlines()) if signature in row),
                    0,
                )
                problems.append(f"mojibake ({name} {_label(signature)}): {path}:{line}")
    return problems, scanned


def _resolve_roots(argv: Sequence[str]) -> tuple[tuple[pathlib.Path, ...], set[pathlib.Path]]:
    """The repository roots by default, or the paths given on the command line.

    This file is skipped only for the default roots: it is pure ASCII by
    construction, and naming it explicitly is a request to scan it.
    """
    if not argv:
        return ROOTS, {SELF_PATH}
    return tuple(pathlib.Path(argument) for argument in argv), set()


def main(argv: Sequence[str] | None = None) -> int:
    roots, skip = _resolve_roots(sys.argv[1:] if argv is None else argv)
    problems, scanned = find_problems(roots, skip=skip)
    for problem in problems:
        print(problem)
    if scanned == 0:
        missing = [str(root) for root in roots if not root.exists()]
        if missing:
            print(f"no source files: missing root(s): {', '.join(missing)}")
        else:
            print(f"no source files: nothing to scan under {', '.join(str(r) for r in roots)}")
        return 2
    verdict = "clean" if not problems else f"{len(problems)} problem(s)"
    print(f"scanned {scanned} files: {verdict}")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
