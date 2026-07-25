import pytest

from rwt_rconsole import (
    CRT_4X3,
    BitDepth,
    ContentFit,
    DisplayConfig,
    PostEffect,
    Size2D,
    video_math,
)


def _valid_cfg(**overrides) -> DisplayConfig:
    base = dict(
        source_size=Size2D(160, 200),
        target_size=Size2D(320, 200),
        bit_depth=BitDepth.BPP4,
        content_fit=ContentFit.LETTERBOX,
        aspect_ratio=CRT_4X3,
        title="Test",
        initial_scale=3,
        effects=(),
    )
    base.update(overrides)
    return DisplayConfig(**base)


def test_buffer_length_design_examples():
    assert video_math.buffer_length(Size2D(160, 200), BitDepth.BPP4) == 16_000
    assert video_math.buffer_length(Size2D(320, 200), BitDepth.BPP8) == 64_000
    assert video_math.buffer_length(Size2D(640, 200), BitDepth.BPP1) == 16_000


def test_palette_length():
    assert video_math.palette_length(BitDepth.BPP1) == 2
    assert video_math.palette_length(BitDepth.BPP4) == 16
    assert video_math.palette_length(BitDepth.BPP8) == 256


def test_scale_factors():
    sx, sy = video_math.scale_factors(Size2D(160, 200), Size2D(320, 200))
    assert sx == 2 and sy == 1


def test_display_config_accepts_good():
    cfg = _valid_cfg()
    assert cfg.source_size.width == 160


def test_display_config_accepts_crt():
    cfg = _valid_cfg(effects=(PostEffect.CRT,))
    assert PostEffect.CRT in cfg.effects


def test_display_config_rejects_odd_width_4bpp():
    with pytest.raises(ValueError, match="even width"):
        _valid_cfg(source_size=Size2D(161, 200), target_size=Size2D(322, 200))


def test_display_config_rejects_width_not_divisible_by_8_1bpp():
    with pytest.raises(ValueError, match="divisible by 8"):
        _valid_cfg(
            bit_depth=BitDepth.BPP1,
            source_size=Size2D(100, 200),
            target_size=Size2D(100, 200),
        )


def test_display_config_rejects_non_multiple_target():
    with pytest.raises(ValueError, match="integer multiples"):
        _valid_cfg(target_size=Size2D(321, 200))


def test_display_config_rejects_bad_scale():
    with pytest.raises(ValueError, match="initial_scale"):
        _valid_cfg(initial_scale=0)


def test_presentation_size_320x200_at_4x3():
    size = video_math.presentation_size(Size2D(320, 200), CRT_4X3)
    assert size == Size2D(320, 240)


def test_initial_window_size():
    size = video_math.initial_window_size(_valid_cfg())
    assert size == Size2D(960, 720)


def test_display_config_rejects_bad_aspect():
    with pytest.raises(ValueError, match="aspect_ratio"):
        _valid_cfg(aspect_ratio=0.0)


def test_size2d_unpacks():
    w, h = Size2D(320, 200)
    assert (w, h) == (320, 200)


def test_screen_to_source_stretch():
    cfg = _valid_cfg(content_fit=ContentFit.STRETCH)
    top_left = video_math.screen_to_source(cfg, (640.0, 400.0), (0.0, 0.0))
    bottom_right = video_math.screen_to_source(cfg, (640.0, 400.0), (639.9, 399.9))
    assert top_left is not None and top_left.x == 0 and top_left.y == 0
    assert bottom_right is not None and bottom_right.x == 159 and bottom_right.y == 199


def test_screen_to_source_letterbox():
    cfg = _valid_cfg(
        source_size=Size2D(320, 200),
        target_size=Size2D(320, 200),
        content_fit=ContentFit.LETTERBOX,
        aspect_ratio=4.0 / 3.0,
    )
    left = video_math.screen_to_source(cfg, (800.0, 480.0), (40.0, 240.0))
    right = video_math.screen_to_source(cfg, (800.0, 480.0), (750.0, 240.0))
    active_tl = video_math.screen_to_source(cfg, (800.0, 480.0), (80.0, 0.0))
    active_br = video_math.screen_to_source(cfg, (800.0, 480.0), (719.9, 479.9))
    assert left is None and right is None
    assert active_tl is not None and active_tl.x == 0 and active_tl.y == 0
    assert active_br is not None and active_br.x == 319 and active_br.y == 199
