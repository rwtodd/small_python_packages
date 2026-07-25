import ctypes

from rwt_rconsole import SharedByteBuffer


def test_memoryview_write():
    buf = SharedByteBuffer(16)
    mv = memoryview(buf)
    assert len(mv) == 16
    mv[0] = 42
    assert buf.view[0] == 42


def test_address_ctypes():
    buf = SharedByteBuffer(8)
    buf.view[3] = 99
    addr = buf.address
    assert addr != 0
    arr = (ctypes.c_uint8 * 8).from_address(addr)
    assert arr[3] == 99
    arr[1] = 7
    # raw address writes do not auto-mark dirty
    assert buf.view[1] == 7


def test_external_pointer_wrap():
    raw = (ctypes.c_uint8 * 4)(1, 2, 3, 4)
    addr = ctypes.addressof(raw)
    buf = SharedByteBuffer(4, address=addr, owner=raw)
    assert list(buf.view) == [1, 2, 3, 4]
    buf.view[0] = 9
    assert raw[0] == 9
