from __future__ import annotations

import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGETS = [
    ROOT / "web" / "src",
    ROOT / "web" / "index.html",
]

TEXT_SUFFIXES = {
    ".css",
    ".html",
    ".ts",
    ".tsx",
}

MOJIBAKE_PATTERNS = [
    ("\ufffd", "unicode replacement character"),
    ("????", "question-mark mojibake"),
    ("Ã", "UTF-8 decoded as Latin-1 mojibake"),
    ("Â", "UTF-8 decoded as Latin-1 mojibake"),
    ("â€", "UTF-8 punctuation mojibake"),
    ("妯", "Chinese text decoded with the wrong legacy code page"),
    ("绛", "Chinese text decoded with the wrong legacy code page"),
    ("鑲", "Chinese text decoded with the wrong legacy code page"),
    ("鏉", "Chinese text decoded with the wrong legacy code page"),
    ("缁", "Chinese text decoded with the wrong legacy code page"),
    ("鍥", "Chinese text decoded with the wrong legacy code page"),
    ("椋", "Chinese text decoded with the wrong legacy code page"),
    ("杈", "Chinese text decoded with the wrong legacy code page"),
    ("寮€", "Chinese text decoded with the wrong legacy code page"),
    ("鏈€", "Chinese text decoded with the wrong legacy code page"),
]

LATIN1_CJK_MOJIBAKE = re.compile(r"[åæçèéäö]{2,}")


def iter_files(targets: list[Path]) -> list[Path]:
    files: list[Path] = []
    for target in targets:
        if target.is_file() and target.suffix in TEXT_SUFFIXES:
            files.append(target)
        elif target.is_dir():
            files.extend(
                path
                for path in target.rglob("*")
                if path.is_file() and path.suffix in TEXT_SUFFIXES
            )
    return sorted(files)


def inspect_file(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    findings: list[str] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for pattern, reason in MOJIBAKE_PATTERNS:
            if pattern in line:
                findings.append(f"{path.relative_to(ROOT)}:{line_no}: {reason}: {line.strip()}")
        if LATIN1_CJK_MOJIBAKE.search(line):
            findings.append(
                f"{path.relative_to(ROOT)}:{line_no}: probable Latin-1 CJK mojibake: {line.strip()}"
            )
    return findings


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify frontend source text has no obvious mojibake.")
    parser.add_argument(
        "targets",
        nargs="*",
        type=Path,
        default=DEFAULT_TARGETS,
        help="Files or directories to scan. Defaults to web/src and web/index.html.",
    )
    args = parser.parse_args()

    targets = [target if target.is_absolute() else ROOT / target for target in args.targets]
    files = iter_files(targets)
    if not files:
        raise SystemExit("No frontend text files found to scan.")

    findings: list[str] = []
    for path in files:
        findings.extend(inspect_file(path))

    if findings:
        print("Frontend text smoke failed:")
        for finding in findings:
            print(f"- {finding}")
        raise SystemExit(1)

    print(f"Frontend text smoke passed: {len(files)} files scanned.")


if __name__ == "__main__":
    main()
