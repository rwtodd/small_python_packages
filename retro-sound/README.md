# rwt_rsound

 ( grok --resume 019f9b39-698c-7db1-9451-09cdc226ff8a )

Retro **sound-chip emulation** for emulators and chiptune work. Cores run in a
small C extension (`rwt_rsound._chips`); Python provides typed façades and MIDI
note helpers.

**This package only synthesizes mono float32 PCM.** Host audio (device pull,
PCM ring, GIL-free drain) lives in optional peer
[`rwt_rconsole`](../retro-console). Offline render needs no host package.

## Install

```bash
cd retro-sound
uv sync --extra dev
```

Requires a C compiler (same pattern as `rwt_rfonts`).

## Chips (current)

| Chip | API | Notes |
|------|-----|--------|
| **IBM PC Speaker** | `PCSpeaker` | PIT-timed tone; default **square**; optional other waveforms |
| **SN76489 family** | `SN76496`, `tandy_sound()`, `sega_psg()` | 3 tone + noise; **Tandy** vs **Sega** LFSR profiles |
| **NES APU** | `NesApu`, `nes_apu_ntsc()` | Pulse ×2, triangle, noise, DMC; **cycle-stepped** for emulators |

Planned: OPL3 (includes OPL2/AdLib), SID, AY-3-8910, Game Boy, YM2612, …

## Quick start — PC Speaker

```python
from rwt_rsound import PCSpeaker, Waveform

spk = PCSpeaker(sample_rate=44100)
spk.beep(440.0)                 # A4 square
buf = spk.render(44100)         # 1 second mono float32

spk.set_waveform(Waveform.TRIANGLE)  # non-historical creative mode
spk.set_pit_divisor(0x0533)     # classic PIT programming
spk.set_gate(True)
```

## Quick start — Tandy / Sega PSG

```python
from rwt_rsound import tandy_sound, sega_psg, SN76496Variant, Waveform

psg = tandy_sound(sample_rate=44100)
psg.note_on(0, 440.0, volume=0)   # channel 0, loud
psg.set_noise(white=True, rate=2, volume=4)
samples = psg.render(22050)

sms = sega_psg(sample_rate=44100)
assert sms.variant is SN76496Variant.SEGA

# TI latch protocol (emulator-style)
psg.write(0x80 | (0 << 4) | 0x0)
psg.write(0x10)

psg.set_tone_waveform(0, Waveform.SINE)  # non-historical
```

## Quick start — NES APU

Advance with the same **CPU cycle** counts as the rest of the machine, then
drain mono PCM for the host ring.

```python
from rwt_rsound import NesApu, NesRegion

apu = NesApu(sample_rate=44100, region=NesRegion.NTSC)
apu.write(0x4015, 0x01)
apu.write(0x4000, 0xBF)
apu.write(0x4002, 0xFD)
apu.write(0x4003, 0x00)

# emu loop:
#   apu.clock(cpu_cycles)
#   n = apu.samples_available()
#   apu.drain_into(buf); ring.push_mono(buf)

apu.set_dmc_reader(lambda addr: memory[addr & 0xFFFF])

# offline:
apu.note_on_pulse(0, 440.0)
samples = apu.render(44100)
```

## Realtime with `rwt_rconsole`

```python
from rwt_rconsole import AudioConfig, PcmRing, create_audio_from_ring
from rwt_rsound import tandy_sound

cfg = AudioConfig(sample_rate=44100, channels=2, reverb=0)
ring = PcmRing(config=cfg, latency_ms=25)
psg = tandy_sound(sample_rate=44100)
psg.note_on(0, 440.0)

with create_audio_from_ring(cfg, ring, frames_per_buffer=256, buffer_count=3) as player:
    player.play()
    # each tick:
    ring.push_mono(psg.render(512))
```

Apps depend on both packages; neither imports the other.

## MIDI notes (convenience only)

```python
from rwt_rsound import tandy_sound, sn76496_note_on, sn76496_note_off

chip = tandy_sound()
sn76496_note_on(chip, channel=0, note=60, velocity=100)
sn76496_note_off(chip, 0)
```

## Design notes

- **Register / control first**, then `render` / `render_into` for PCM.
- **Game-agnostic**: no engine resource formats here.
- **Tandy vs Sega** share one SN76489 core (`SN76496Variant`).
- Non-square waveforms on PC Speaker / SN tone channels are creative options.

## License

MIT
