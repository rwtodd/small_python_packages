"""Private CLI entry point for the `bascat` tool.

This module is **not** part of the public library API of rwt_bascat.
It is only imported by the console-script entry point created during
installation (especially via `uv tool install .`).

Library users should do:  `from rwt_bascat import BasicFile`
"""

from __future__ import annotations

import argparse

from rwt_bascat import BasicFile


def decode(fname: str) -> None:
    with open(fname, "rb") as infile:
        data = infile.read()
    for line in BasicFile(data):
        print(line)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="BASCAT: decode tokeninzed GWBASIC/BASICA files"
    )
    parser.add_argument("filename", type=str, default=None, nargs="*")
    args = parser.parse_args()
    for fname in args.filename:
        decode(fname)