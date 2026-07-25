from rwt_rconsole import BitDepth, FrameBuffer, Size2D, get_pixel, set_pixel


def test_4bpp_high_nibble_is_left_pixel():
    size = Size2D(4, 1)
    fb = FrameBuffer(size, BitDepth.BPP4)
    fb[0, 0] = 0xA
    fb[1, 0] = 0x5
    assert fb.view[0] == 0xA5
    assert fb[0, 0] == 0xA
    assert fb[1, 0] == 0x5


def test_1bpp_msb_is_leftmost():
    size = Size2D(8, 1)
    fb = FrameBuffer(size, BitDepth.BPP1)
    fb[0, 0] = 1
    fb[7, 0] = 1
    assert fb.view[0] == 0b1000_0001
    assert fb[0, 0] == 1
    assert fb[1, 0] == 0
    assert fb[7, 0] == 1


def test_8bpp_round_trip():
    size = Size2D(2, 2)
    fb = FrameBuffer(size, BitDepth.BPP8)
    fb[1, 1] = 42
    assert fb[1, 1] == 42


def test_160x200_4bpp_buffer_length():
    fb = FrameBuffer(Size2D(160, 200), BitDepth.BPP4)
    assert len(fb) == 16_000


def test_packed_indices_round_trip():
    cases = [
        (BitDepth.BPP1, Size2D(16, 2), [(0, 0, 1), (7, 0, 1), (8, 0, 0), (15, 1, 1)]),
        (BitDepth.BPP4, Size2D(8, 2), [(0, 0, 0xA), (1, 0, 0x5), (2, 1, 0xF), (7, 1, 0x3)]),
        (BitDepth.BPP8, Size2D(4, 2), [(0, 0, 0), (3, 0, 255), (1, 1, 42)]),
    ]
    for depth, size, pixels in cases:
        fb = FrameBuffer(size, depth)
        for x, y, idx in pixels:
            fb[x, y] = idx
        for x, y, idx in pixels:
            assert fb[x, y] == idx


def test_free_functions_still_work():
    size = Size2D(4, 1)
    fb = FrameBuffer(size, BitDepth.BPP4)
    set_pixel(fb.data, BitDepth.BPP4, size, 0, 0, 0xC)
    assert get_pixel(fb.data, BitDepth.BPP4, size, 0, 0) == 0xC
