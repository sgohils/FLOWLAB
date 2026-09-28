"""Guard against encoding damage in the sources.

Four files were once edited through a Windows PowerShell pipeline that read
UTF-8 as ANSI and wrote it back, turning an em dash into three characters.
The symptom is visible in the interface ("1280 x 720" with a broken glyph) and
is easy to miss in a diff, so this check runs as part of the verification pass.

The signatures are built from code points so this file is pure ASCII and can
never report itself.
"""

from __future__ import annotations

import pathlib
import sys

ROOTS = (pathlib.Path("frontend/src"), pathlib.Path("backend"), pathlib.Path("docs"))
SUFFIXES = {".ts", ".tsx", ".py", ".md", ".css", ".html", ".json"}


def _chars(*codepoints: int) -> str:
    return "".join(chr(codepoint) for codepoint in codepoints)


#: Byte sequences that only appear when UTF-8 has been decoded as cp1252.
SIGNATURES = {
    _chars(0xE2, 0x20AC, 0x94): "em dash",
    _chars(0xE2, 0x20AC, 0xB7): "middle dot",
    _chars(0xE2, 0x20AC, 0xA6): "ellipsis",
    _chars(0xC3, 0xA9): "accented letter",
    _chars(0xC2, 0xA0): "non-breaking space",
    _chars(0xEF, 0xBF, 0xBD): "replacement character",
}


def main() -> int:
    self_path = pathlib.Path(__file__).resolve()
    problems: list[str] = []
    scanned = 0
    for root in ROOTS:
        paths = [root] if root.is_file() else sorted(root.rglob("*"))
        for path in paths:
            if not path.is_file() or path.suffix not in SUFFIXES:
                continue
            if path.resolve() == self_path:
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
                if signature in text:
                    line = next(
                        (i + 1 for i, row in enumerate(text.splitlines()) if signature in row),
                        0,
                    )
                    problems.append(f"mojibake ({name}): {path}:{line}")
    for problem in problems:
        print(problem)
    print(f"scanned {scanned} files: " + ("clean" if not problems else f"{len(problems)} problem(s)"))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
