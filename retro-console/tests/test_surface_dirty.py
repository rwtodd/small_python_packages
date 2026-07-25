from rwt_rconsole import BitDepth, FrameBuffer, Palette, RgbColor, SharedByteBuffer, Size2D


def test_shared_buffer_dirty():
    buf = SharedByteBuffer(100)
    assert buf.dirty
    buf.clear_dirty()
    assert not buf.dirty
    _ = buf.view
    assert buf.dirty
    buf.clear_dirty()
    assert not buf.dirty
    _ = memoryview(buf)
    assert buf.dirty


def test_framebuffer_dirty():
    fb = FrameBuffer(Size2D(8, 1), BitDepth.BPP8)
    fb.clear_dirty()
    fb[0, 0] = 1
    assert fb.dirty


def test_palette_dirty():
    pal = Palette(BitDepth.BPP4)
    assert pal.dirty
    pal.clear_dirty()
    assert not pal.dirty
    pal[0] = RgbColor(255, 0, 0)
    assert pal.dirty
    pal.clear_dirty()
    assert not pal.dirty
    pal.update([(0, 255, 0)])
    assert pal.dirty
