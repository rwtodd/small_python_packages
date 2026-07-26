"""rwt_rsound — retro sound-chip emulation for emulators and chiptune.

Synthesis only: control chips and render mono float32 PCM. Host audio
(device pull, PCM ring) lives in ``rwt_rconsole``.
"""

from .chip import SoundChip, Waveform
from .midi import (
    hz_to_midi_note,
    midi_note_to_hz,
    nes_pulse_note_off,
    nes_pulse_note_on,
    pc_speaker_note_off,
    pc_speaker_note_on,
    sn76496_note_off,
    sn76496_note_on,
    velocity_to_nes_volume,
    velocity_to_sn_volume,
)
from .nes_apu import (
    NTSC_CPU_HZ,
    PAL_CPU_HZ,
    NesApu,
    NesRegion,
    nes_apu_ntsc,
    nes_apu_pal,
)
from .pc_speaker import PIT_CLOCK_HZ, PCSpeaker
from .render import render_mono_to_stereo
from .sn76496 import (
    DEFAULT_CLOCK_HZ,
    SN76496,
    SN76496Variant,
    sega_psg,
    tandy_sound,
)

__all__ = [
    "SoundChip",
    "Waveform",
    "PCSpeaker",
    "PIT_CLOCK_HZ",
    "SN76496",
    "SN76496Variant",
    "DEFAULT_CLOCK_HZ",
    "tandy_sound",
    "sega_psg",
    "NesApu",
    "NesRegion",
    "NTSC_CPU_HZ",
    "PAL_CPU_HZ",
    "nes_apu_ntsc",
    "nes_apu_pal",
    "render_mono_to_stereo",
    "midi_note_to_hz",
    "hz_to_midi_note",
    "velocity_to_sn_volume",
    "velocity_to_nes_volume",
    "sn76496_note_on",
    "sn76496_note_off",
    "nes_pulse_note_on",
    "nes_pulse_note_off",
    "pc_speaker_note_on",
    "pc_speaker_note_off",
]

__version__ = "1.0"
