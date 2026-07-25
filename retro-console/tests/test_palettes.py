import pytest

from rwt_rconsole import (
    CRT_4X3,
    BitDepth,
    ContentFit,
    DisplayConfig,
    Palette,
    Size2D,
    cga,
    clear_display_backend,
    create_display,
    ega,
    for_bit_depth,
    monochrome,
    vga,
)


def test_palette_sizes():
    assert len(monochrome) == 2
    assert len(cga) == 16
    assert len(ega) == 16
    assert len(vga) == 256


def test_for_bit_depth_sizes():
    assert len(for_bit_depth(BitDepth.BPP1)) == 2
    assert len(for_bit_depth(BitDepth.BPP4)) == 16
    assert len(for_bit_depth(BitDepth.BPP8)) == 256


def test_palette_seeds_from_defaults():
    p = Palette(BitDepth.BPP4)
    assert len(p) == 16
    assert p[15] == ega[15]


def test_palette_accepts_tuple():
    p = Palette(4)
    p[0] = (255, 128, 0)
    assert p[0].r == 255 and p[0].g == 128 and p[0].b == 0


def test_create_without_backend_throws():
    clear_display_backend()
    cfg = DisplayConfig(
        source_size=Size2D(160, 200),
        target_size=Size2D(320, 200),
        bit_depth=BitDepth.BPP4,
        content_fit=ContentFit.LETTERBOX,
        aspect_ratio=CRT_4X3,
        title="Test",
        initial_scale=2,
    )
    with pytest.raises(RuntimeError, match="No display backend"):
        create_display(cfg)
