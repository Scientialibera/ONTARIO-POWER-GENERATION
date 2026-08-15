from __future__ import annotations

from pathlib import Path
import sys


TEXT_SUFFIXES = {
    ".css", ".html", ".js", ".json", ".md", ".py", ".toml", ".ts", ".tsx",
    ".txt", ".yaml", ".yml",
}
EMOJI_RANGES = (
    (0x00A9, 0x00A9), (0x00AE, 0x00AE), (0x203C, 0x203C),
    (0x2049, 0x2049), (0x20E3, 0x20E3), (0x2122, 0x2122),
    (0x2139, 0x2139), (0x2194, 0x21FF), (0x2300, 0x23FF),
    (0x24C2, 0x24C2), (0x25AA, 0x27BF), (0x2B00, 0x2BFF),
    (0x3030, 0x3030), (0x303D, 0x303D), (0x3297, 0x3297),
    (0x3299, 0x3299), (0x1F000, 0x1FAFF), (0xFE0F, 0xFE0F),
)


def is_emoji(character: str) -> bool:
    codepoint = ord(character)
    return any(start <= codepoint <= end for start, end in EMOJI_RANGES)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    violations = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in {".git", ".venv", "__pycache__", "node_modules"} for part in path.parts):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name != "Dockerfile":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(text.splitlines(), 1):
            if any(is_emoji(character) for character in line):
                violations.append(f"{path.relative_to(root)}:{line_number}")
    if violations:
        print("Emoji policy violations:")
        for item in violations:
            print(item)
        return 1
    print("No emoji characters found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
