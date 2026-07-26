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

### Recommended: PCM ring + pure-C AudioQueue drain (no GIL)

Host audio is a **pull** model. Producers (emulators, `rwt_rsound` chips, etc.)
**push** float32 frames into a ring; the device drains it from a **native C**
callback (no Python on the audio thread).

```python
from rwt_rconsole import (
    AudioConfig, AudioChannels, PcmRing, create_audio_from_ring,
    DEFAULT_LATENCY_MS, DEFAULT_FRAMES_PER_BUFFER, DEFAULT_BUFFER_COUNT,
)
import math, struct, time

cfg = AudioConfig(sample_rate=44100, channels=AudioChannels.STEREO, reverb=0)

# Application-side buffer (~25 ms by default). Fully tunable via latency_ms
# or capacity_frames.
ring = PcmRing(config=cfg, latency_ms=25)

# Device queue depth is ALSO tunable — Apple does not require 3×512.
# defaults: frames_per_buffer=256, buffer_count=3
# approx device latency ≈ buffer_count * frames_per_buffer / sample_rate
player = create_audio_from_ring(
    cfg, ring,
    frames_per_buffer=256,
    buffer_count=3,
)

# Producer (emu loop / thread): push mono or interleaved float32
phase = 0.0
def produce(n_frames: int) -> None:
    global phase
    samples = []
    for _ in range(n_frames):
        samples.append(math.sin(phase) * 0.2)
        phase += 2 * math.pi * 440 / cfg.sample_rate
    ring.push_mono(struct.pack(f"{n_frames}f", *samples))

with player:
    player.play()
    for _ in range(100):
        produce(512)
        time.sleep(512 / cfg.sample_rate)
```

| Knob | Default | Meaning |
|------|---------|---------|
| `PcmRing(latency_ms=…)` | **25 ms** | How much app-side PCM you can queue |
| `PcmRing(capacity_frames=…)` | from latency | Explicit ring size in frames |
| `frames_per_buffer` | **256** | Size of each AudioQueue buffer (was 512 in the old Python callback path) |
| `buffer_count` | **3** | AQ buffers in flight (not an OS requirement) |

Total latency ≈ **ring fill** (how full you keep it) + **device** (`buffer_count × frames_per_buffer`).

### Legacy: Python callback path

Still available for demos/tests (runs Python on the AudioQueue thread → GIL):

```python
from rwt_rconsole import AudioConfig, create_audio, as_float32, suggested_audio_config
from rwt_rconsole.backends.apple_audio import register as register_audio

register_audio()
cfg = suggested_audio_config()

def callback(dst: memoryview) -> None:
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
