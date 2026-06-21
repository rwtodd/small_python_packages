"""Private CLI entry point for the `unromanize` tool."""

from __future__ import annotations

import argparse
import fileinput

from rwt_romanized import greek, hebrew


def to_entity(ch: str) -> str:
    numeric = ord(ch)
    if numeric < 128:
        return ch
    return f"&#x{numeric:04x};"


def process_hebrew(line: str) -> None:
    unicode = hebrew(line)
    print(unicode)
    entities = "".join(to_entity(ch) for ch in unicode)
    print("{{hebrew text|", entities, "}}", sep="")


def process_greek(line: str) -> None:
    unicode = greek(line)
    print(unicode)
    entities = "".join(to_entity(ch) for ch in unicode)
    print(entities)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert hebrew or greek romanized text to Unicode."
    )
    parser.add_argument(
        "-l",
        "--lang",
        dest="language",
        default="heb",
        choices=["heb", "grk"],
        help="Choose the language (default heb)",
    )
    parser.add_argument("filenames", metavar="filename", type=str, nargs="*")
    args = parser.parse_args()

    match args.language:
        case "heb":
            processor = process_hebrew
        case "grk":
            processor = process_greek

    with fileinput.input(args.filenames) as f:
        for line in f:
            processor(line.rstrip())