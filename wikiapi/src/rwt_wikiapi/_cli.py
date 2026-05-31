"""Private CLI entry point for the `wiki-xfer` tool.

This module is **not** part of the public library API of rwt_wikiapi.
It is only imported by the console-script entry point created during
installation (especially via `uv tool install .`).

Library users should do:  `from rwt_wikiapi import Client, ...`
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import rwt_wikiapi as wiki


def _read_credentials(path: str) -> dict[str, str]:
    """Load credentials from a JSON file.

    Accepts both the new keys (base_url, username, password) and the
    older legacy keys (url, uname, pw) for transition convenience.
    """
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f) or {}
    except FileNotFoundError:
        sys.exit(f"Credentials file not found: {path}")
    except json.JSONDecodeError as e:
        sys.exit(f"Invalid JSON in credentials file: {e}")

    base_url = raw.get("base_url") or raw.get("url")
    username = raw.get("username") or raw.get("uname")
    password = raw.get("password") or raw.get("pw")

    if not (base_url and username and password):
        sys.exit(
            'Credentials file must contain "base_url" (or "url"), '
            '"username" (or "uname"), and "password" (or "pw")'
        )
    return {"base_url": base_url, "username": username, "password": password}


def _read_null_filenames() -> list[str]:
    """Read NUL-separated filenames from stdin (for find -print0 etc.)."""
    if sys.stdin.isatty():
        return []
    sys.stdin.reconfigure(encoding="utf-8", errors="surrogateescape")
    data = sys.stdin.buffer.read()
    return [s for s in data.decode("utf-8", errors="surrogateescape").split("\0") if s]


def _print_example_creds() -> None:
    print(
        """# wiki_creds.json
{
  "base_url": "https://mywiki.example.com/w",
  "username": "your-username",
  "password": "your-password"
}
"""
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="wiki-xfer",
        description="Upload/download articles and media files to/from a MediaWiki site",
    )
    parser.add_argument(
        "-c",
        "--creds",
        default="wiki_creds.json",
        help="JSON credentials file (default: wiki_creds.json)",
    )
    parser.add_argument(
        "-s",
        "--summary",
        default="Uploaded file {}",
        help='Summary/comment. {} is replaced by the filename (default: "Uploaded file {}")',
    )
    parser.add_argument(
        "--html",
        action="append",
        default=[],
        metavar="TITLE",
        help="Fetch page as HTML (repeatable)",
    )
    parser.add_argument(
        "--wiki",
        action="append",
        default=[],
        metavar="TITLE",
        help="Fetch page as wikitext (repeatable)",
    )
    parser.add_argument(
        "--media",
        action="append",
        default=[],
        metavar="TITLE",
        help="Fetch media file as binary (repeatable)",
    )
    parser.add_argument(
        "--example-creds",
        action="store_true",
        help="Print an example credentials file and exit",
    )
    parser.add_argument(
        "-0",
        "--null",
        action="store_true",
        help="Read additional NUL-separated (\\0) filenames from STDIN",
    )
    parser.add_argument(
        "files",
        nargs="*",
        metavar="FILE",
        help="Files to upload (images) or edit (everything else)",
    )

    args = parser.parse_args()

    if args.example_creds:
        _print_example_creds()
        return

    # Collect work items
    html_titles: list[str] = args.html
    wiki_titles: list[str] = args.wiki
    media_titles: list[str] = args.media
    upload_files: list[str] = list(args.files)

    if args.null:
        upload_files.extend(_read_null_filenames())

    total = len(html_titles) + len(wiki_titles) + len(media_titles) + len(upload_files)
    if total == 0:
        # Nothing to do — silent success (matches Ruby/Go behavior)
        return

    creds = _read_credentials(args.creds)

    try:
        with wiki.Client.session(
            creds["base_url"], creds["username"], creds["password"]
        ) as client:
            # --- Fetches (in grouped order, like the Ruby driver) ---
            for title in html_titles:
                try:
                    html = client.fetch_html(title)
                    fname = title.replace(" ", "_") + ".html"
                    with open(fname, "w", encoding="utf-8") as f:
                        f.write(html)
                    print(f"Wrote {fname}")
                except wiki.Error as e:
                    sys.exit(f"Error processing {title}: {e}")

            for title in wiki_titles:
                try:
                    text = client.fetch_wikitext(title)
                    fname = title.replace(" ", "_") + ".wikitext"
                    with open(fname, "w", encoding="utf-8") as f:
                        f.write(text)
                    print(f"Wrote {fname}")
                except wiki.Error as e:
                    sys.exit(f"Error processing {title}: {e}")

            for title in media_titles:
                try:
                    data = client.fetch_media(title)
                    fname = wiki.normalize_filename(title)
                    with open(fname, "wb") as f:
                        f.write(data)
                    print(f"Wrote {fname} ({len(data)} bytes)")
                except wiki.Error as e:
                    sys.exit(f"Error processing {title}: {e}")

            # --- Uploads / edits ---
            for path in upload_files:
                try:
                    summary = args.summary.replace("{}", os.path.basename(path))
                    if wiki.uploadable_image(path):
                        client.upload_file(path, comment=summary)
                    else:
                        client.edit_file(path, summary=summary)
                    print(path)
                except wiki.Error as e:
                    sys.exit(f"Error sending {path}: {e}")

    except wiki.LoginError as e:
        sys.exit(f"Login failed: {e}")
    except wiki.Error as e:
        sys.exit(f"Failed to connect/login: {e}")
    except Exception as e:
        # Catch-all for network, DNS, requests exceptions, etc. — give a short message
        sys.exit(f"Failed: {e}")


if __name__ == "__main__":
    main()
