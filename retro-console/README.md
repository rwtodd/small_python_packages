# rwt_rconsole

( grok --resume 019f97e3-eeaf-71d1-934e-1748b00a477d )

Memory-backed retro paletted display and streaming audio for Python.

Packed 1/4/8 bpp VRAM, stock palettes, Metal presentation on macOS, and AudioQueue streaming.

## Install

```bash
# core (pure Python)
uv sync

# with Metal display backend (macOS)
uv sync --extra metal --extra dev
```

## Quick start — display

```python
from rwt_rconsole import (
    DisplayConfig, Size2D, BitDepth, ContentFit,
    CRT_4X3, vga, create_display,
)
from rwt_rconsole.backends.metal import register as register_metal

register_metal()

config = DisplayConfig(
    source_size=Size2D(320, 200),
    target_size=Size2D(320, 200),
    bit_depth=BitDepth.BPP8,
    content_fit=ContentFit.LETTERBOX,
    aspect_ratio=CRT_4X3,
    title="HelloRetro",
    initial_scale=3,
)

with create_display(config) as display:
    display.palette.update(vga)
    print(f"Display refresh ≈ {display.refresh_rate:.1f} Hz")
    frame = 0

    def on_frame(d):
        nonlocal frame
        mv = d.buffer.view          # packed uint8 VRAM
        # … or d.buffer[x, y] = index for single pixels …
        frame += 1
        return True                 # present this frame (False to skip GPU work)

    # run() is paced by CVDisplayLink (one wake per display refresh),
    # then throttled so on_frame runs at most `fps` times per second.
    display.run(30.0, on_frame)
```

Query the main display without opening a window:

```python
from rwt_rconsole.backends.metal import main_display_refresh_rate
print(main_display_refresh_rate())  # e.g. 60.0 or 120.0
```

## Buffer interop

`FrameBuffer` implements the **buffer protocol** over packed VRAM:

```python
memoryview(display.buffer)        # writable uint8
display.buffer.address            # native pointer for ctypes / C extensions
display.buffer[x, y] = 14         # palette index (handles packing)
display.buffer.mark_dirty()       # after raw pointer writes
```

From another C extension in-process:

```c
Py_buffer view;
PyObject_GetBuffer(framebuffer_obj, &view, PyBUF_WRITABLE | PyBUF_C_CONTIGUOUS);
/* view.buf, view.len */
PyBuffer_Release(&view);
```

## Audio

```python
from rwt_rconsole import AudioConfig, create_audio, as_float32, suggested_audio_config
from rwt_rconsole.backends.apple_audio import register as register_audio
import math

register_audio()
cfg = suggested_audio_config()
phase = 0.0

def callback(dst: memoryview) -> None:
    global phase
    floats = as_float32(dst)
    ...

with create_audio(cfg, callback) as audio:
    audio.play()
```

## Examples

```bash
uv run --extra metal python examples/hello_retro.py --crt --fps 30
uv run --extra metal python examples/palette_cycle.py --crt --fps 30
uv run --extra metal python examples/input_demo.py --crt --fps 60
uv run python examples/audio_demo.py
```

## Tests

```bash
uv run --extra dev pytest
```

## License

MIT
