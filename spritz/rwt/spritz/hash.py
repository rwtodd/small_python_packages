from . import _internal

def hash_buffer(buffer, size:int|bytearray=32) -> bytearray:
    """Hash the given buffer into and return `size`-bytes of hash data.
    If `size` is not an int, it is assumed to be a writeable buffer of the
    desired size already, and is used for the hash bytes."""
    k = _internal.SpritzKernel()
    k.absorb(buffer)
    k.absorb_stop()
    if isinstance(size, int):
        hash = bytearray(size)
    else:
        hash, size = size, len(size)
    k.absorb_number(size)
    k.drip(hash)
    return hash

def hash_file(fname, size:int|bytearray=32) -> bytearray:
    """Hash the given file and return `size`-bytes of hash data.
    If `size` is not an int, it is assumed to be a writeable buffer of the
    desired size already, and is used for the hash bytes."""
    k = _internal.SpritzKernel()
    with open(fname, 'rb') as f:
        buffer = bytearray(8196)
        mv = memoryview(buffer)
        while True:
            bytes_read = f.readinto(buffer)
            if bytes_read == 0:
                break
            k.absorb(mv[:bytes_read])
    k.absorb_stop()
    if isinstance(size, int):
        hash = bytearray(size)
    else:
        hash, size = size, len(size)
    k.absorb_number(size)
    k.drip(hash)
    return hash
