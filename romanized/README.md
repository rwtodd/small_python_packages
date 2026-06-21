# rwt-romanized

Provides a `rwt_romanized` module for converting romanized greek and hebrew
into unicode.

## Installation

### As a library

```bash
uv pip install .
# or
pip install .
```

Then:

```python
from rwt_romanized import greek, hebrew
```

### The `unromanize` CLI tool

```bash
uv tool install .

unromanize -l grk file.txt
```

After installation the `unromanize` command is on your `$PATH`.

Run tests with:

```bash
uv run python -m unittest discover -s tests
```