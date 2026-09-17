"""Fail if any tracked text file contains an emoji. House style: no emojis."""

import re
import subprocess
import sys

EMOJI = re.compile("[\U0001f000-\U0001faff☀-➿⭐⭕⬛⬜️‍‼⁉⌚⌛⏩-⏺]")


def main() -> int:
    files = subprocess.run(
        ["git", "ls-files"], capture_output=True, text=True, check=True
    ).stdout.split()
    problems = []
    for path in files:
        try:
            with open(path, encoding="utf-8") as f:
                for line_no, line in enumerate(f, start=1):
                    if EMOJI.search(line):
                        problems.append(f"{path}:{line_no}: {line.strip()[:80]}")
        except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
            continue
    for p in problems:
        print(p)
    if problems:
        print(f"\n{len(problems)} line(s) contain emojis. Remove them.")
        return 1
    print("No emojis found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
