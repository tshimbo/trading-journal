"""Fail if any tracked text file contains an emoji. House style: no emojis.

Code point ranges are written as integers on purpose, so formatters can never
turn them into literal emoji characters inside this file.
"""

import subprocess
import sys

EMOJI_RANGES = [
    (0x1F000, 0x1FAFF),  # pictographs, emoticons, transport, flags, symbols
    (0x2600, 0x27BF),  # miscellaneous symbols and dingbats
    (0x2B1B, 0x2B1C),  # large squares
    (0x2B50, 0x2B50),  # star
    (0x2B55, 0x2B55),  # circle
    (0x231A, 0x231B),  # watch, hourglass
    (0x23E9, 0x23FA),  # media control symbols
    (0xFE0F, 0xFE0F),  # emoji presentation selector
    (0x200D, 0x200D),  # zero-width joiner used in emoji sequences
]


def is_emoji(char: str) -> bool:
    code = ord(char)
    return any(low <= code <= high for low, high in EMOJI_RANGES)


def main() -> int:
    listing = subprocess.run(["git", "ls-files", "-z"], capture_output=True, check=True)
    problems = []
    for raw in listing.stdout.split(b"\0"):
        if not raw:
            continue
        path = raw.decode()
        try:
            with open(path, encoding="utf-8") as f:
                for line_no, line in enumerate(f, start=1):
                    if any(is_emoji(c) for c in line):
                        problems.append(f"{path}:{line_no}: {line.strip()[:80]}")
        except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
            continue
    for problem in problems:
        print(problem)
    if problems:
        print(f"\n{len(problems)} line(s) contain emojis. Remove them.")
        return 1
    print("No emojis found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
