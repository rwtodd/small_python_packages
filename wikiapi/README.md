# rwt-wikiapi

A small, ergonomic Python library and CLI tool for pushing and pulling wikitext
articles and media files to/from a MediaWiki site.

## Installation

### As a library (pure `import`, no CLI binary)

```bash
uv pip install .
# or
pip install .
```

Then:

```python
from rwt_wikiapi import Client

with Client.session(
    base_url="https://mywiki.example.com/w",
    username=os.environ["WIKI_USER"],
    password=os.environ["WIKI_PASS"],
) as client:
    client.edit("Project:Sandbox", "Hello from Python!\n", summary="test edit")
    client.upload_file("diagram.svg", comment="new diagram for {}")

    text = client.fetch_wikitext("Main Page")
    bytes_ = client.fetch_media("Logo.png")
    Path("Logo.png").write_bytes(bytes_)
```

### The `wiki-xfer` CLI tool

```bash
# Installs the tool (and its isolated copy of the library) into your user environment
uv tool install .

wiki-xfer --help
```

After installation the `wiki-xfer` command is on your `$PATH`.

## Quick Usage (library)

```python
import os
from pathlib import Path
import rwt_wikiapi as wiki

# Pure helper (no login, no network)
url = wiki.raw_media_url("https://mywiki.example.com/w", "My Photo.png")
# => "https://mywiki.example.com/w/images/3/3f/My_Photo.png"

print(wiki.uploadable_image("photo.png"))   # True
print(wiki.image_extensions())
```

## CLI (`wiki-xfer`)

```bash
# Fetch
wiki-xfer -c wiki_creds.json --html "Main Page" --wiki "Help:Foo" --media "Logo.png"

# Push (auto-dispatch: images → upload, everything else → edit)
wiki-xfer -c wiki_creds.json -s "Imported via Python {}" \
          article.wikitext photo.png notes.txt

# Pipe \0-separated list of files (requires -0)
find . -name '*.png' -print0 | wiki-xfer -c wiki_creds.json -s "bulk import {}" -0

# Show example credentials file
wiki-xfer --example-creds
```

Credentials file (`wiki_creds.json`):

```json
{
  "base_url": "https://mywiki.example.com/w",
  "username": "alice",
  "password": "secret"
}
```

Legacy keys (`url` / `uname` / `pw`) are also accepted for transition.

## Design Goals

* Very small surface area — exactly the operations needed for personal wiki maintenance.
* Idiomatic Python (context managers, `**` kwargs, dataclasses not required).
* Only one runtime dependency (`requests`).
* The `raw_media_url` / `normalize_filename` helpers are deliberately pure functions.
* The CLI is deliberately kept in a private `_cli` module so that a plain
  `pip install rwt-wikiapi` gives you a clean library import surface.

## License

MIT — see the `LICENSE` file.
