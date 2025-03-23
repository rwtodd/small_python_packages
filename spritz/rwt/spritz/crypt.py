from . import _internal
from . import hash as _hash
from typing import BinaryIO
import os # for urandom

def _keygen(passw: str, iv: bytes, rounds: int = 30_000) -> _internal.SpritzKernel:
    """Perform keygen on password `passw` and initializatino vector `iv` for `rounds` rounds.
    Return an initialized SpritzKernel that's absorbed the resulting key."""
    if len(iv) < 4:
        raise ValueError('IV for keygen must be at least 4 bytes!')
    iv = bytearray(iv)
    kernel = _internal.SpritzKernel()
    passbytes = _hash.hash_buffer(passw.encode(), 64)
    for _ in range(rounds + iv[3]):
        kernel.absorb(iv)
        kernel.absorb_stop()
        kernel.absorb(passbytes)
        kernel.xor(passbytes)
        kernel.xor(iv)
    # ok, so take our final IV and passbytes and start fresh...
    kernel.reset()
    kernel.absorb(passbytes)
    kernel.absorb_stop()
    kernel.absorb(iv)
    return kernel

def _read_exact(file: BinaryIO, buffer: bytearray) -> None:
    """Read exactly the size of the buffer, or there is an error!"""
    n = len(buffer)  # Size of the provided buffer
    bytes_read = 0
    mv = memoryview(buffer) 
    while bytes_read < n:
        chunk_size = file.readinto(mv[bytes_read:])  # Read into remaining space
        if chunk_size == 0:  # EOF reached
            raise EOFError(f"Expected {n} bytes, but only read {bytes_read}")
        bytes_read += chunk_size

class _Header:
    def __init__(self):
        self._iv = None
        self._key = None

    @property
    def iv(self) -> bytes:
        """The Initialization Vector for the header... 4 bytes"""
        if self._iv is None:
            self._iv = os.urandom(4)
        return self._iv
    @iv.setter
    def iv(self, value: bytes) -> None:
        if len(value) != 4:
            raise ValueError('Initialization Vector must by 4 bytes!')
        self._iv = value

    @property
    def key(self) -> bytes:
        """The encryption key for the payload"""
        if self._key is None:
            self._key = os.urandom(64)
        return self._key
    @key.setter
    def key(self, value: bytes) -> None:
        if len(value) != 64:
            raise ValueError('Encryption key must by 64 bytes!')
        self._key = value

    def read(self, file: BinaryIO, passw: str) -> None:
        tmp = bytearray(4)
        _read_exact(file, tmp)
        pass_hash = _hash.hash_buffer(passw.encode('utf-8'), 4)
        self.iv = bytes(tmp[i] ^ pass_hash[i] for i in range(4))
        cipher = _keygen(passw, self.iv)
        header = bytearray(72)
        _read_exact(file, header)
        header_mv = memoryview(header)
        cipher.xor(header_mv[:4])
        cipher.skip(header[3])
        cipher.xor(header_mv[4:])
        _hash.hash_buffer(header_mv[:4],tmp)
        if memoryview(tmp) != header_mv[4:8]:
            raise ValueError('The header or password is invalid!')
        self.key = bytes(header_mv[8:])

    def write(self, file: BinaryIO, passw: str) -> None:
        file_iv = _hash.hash_buffer(passw.encode('utf-8'), 4)
        for i in range(4): file_iv[i] ^= self.iv[i]
        file.write(file_iv)
        cipher = _keygen(passw, self.iv)
        rnd_bytes = bytearray(os.urandom(4))
        to_skip = rnd_bytes[3]
        hashed_bytes = _hash.hash_buffer(rnd_bytes, 4)
        cipher.xor(rnd_bytes)
        cipher.skip(to_skip)
        cipher.xor(hashed_bytes)
        file.write(rnd_bytes)
        file.write(hashed_bytes)
        enc_key = bytearray(self.key)
        cipher.xor(enc_key)
        file.write(enc_key)

def _do_crypt(infile: BinaryIO, outfile:BinaryIO, kernel: _internal.SpritzKernel) -> None:
    """Helper function to finish the encryption/decryption process."""
    buffer = bytearray(8196)
    mv = memoryview(buffer)
    while True:
       bytes_read = infile.readinto(buffer)
       if bytes_read == 0:
          break
       the_bytes = mv[:bytes_read]
       kernel.xor(the_bytes)
       outfile.write(the_bytes)

def encrypt(passw: str, orig_fname: str, infile: BinaryIO, outfile: BinaryIO) -> None:
    """Encrypt `infile` with spritz, password `passw`. Write the result
    to `outfile`"""
    header = _Header()
    header.write(outfile, passw)
    kernel = _internal.SpritzKernel()
    kernel.absorb(header.key)
    kernel.skip(134 + header.key[3])
    name_len = len(orig_fname)
    if name_len.bit_length() > 16:
        raise ValueError('Original filename is longer than 16k chars!')
    tmp  = bytearray(name_len.to_bytes(2, byteorder='big'))
    kernel.xor(tmp)
    outfile.write(tmp)
    if name_len > 0:
      tmp = bytearray(orig_fname.encode('utf-8'))
      kernel.xor(tmp)
      outfile.write(tmp)
    _do_crypt(infile, outfile, kernel)

def decrypt(passw: str, infile: BinaryIO, outfile: BinaryIO|None = None) -> str:
    """Decrypt `infile` with spritz, password `passw`. Write the result
    to `outfile`.  `outfile` can be an open binary file, or None.  When it
    is None, this function will open a file with the name stored inside the
    encrypted file.  If no name was stored the name will be 'unknown_name'.
    The file stored as the original filename in the encrypted input is returned."""
    header = _Header()
    header.read(infile, passw)
    kernel = _internal.SpritzKernel()
    kernel.absorb(header.key)
    kernel.skip(134 + header.key[3])
    tmp = bytearray(2) 
    _read_exact(infile, tmp)
    kernel.xor(tmp)
    fname_len = int.from_bytes(tmp, byteorder='big')
    if fname_len == 0:
        orig_fname = 'unknown_name'
    else:
        tmp = bytearray(fname_len)
        _read_exact(infile, tmp)
        kernel.xor(tmp)
        orig_fname = tmp.decode('utf-8')
    if outfile is None:
        with open(orig_fname, 'wb') as new_outfile:
            _do_crypt(infile, new_outfile, kernel)
    else:
        _do_crypt(infile, outfile, kernel)
    return orig_fname

def check(passw: str, infile: BinaryIO) -> bool:
    """Check if the password appears to unlock the given input, but don't decrypt
    the payload if it does. Just return True for yes and False for no."""
    try:
        header = _Header()
        header.read(infile, passw)
    except ValueError:
        return False
    return True

def change_password(old_passw: str, new_passw: str, file: BinaryIO) -> None:
    """Change the password for a file without fully re-encrypting... just change the
    header and keep the original encryption key.  If `file` is on disk, it must be 
    opened 'r+b' so that both reading and writing work."""
    header = _Header()
    file.seek(0)
    header.read(file, old_passw)
    header.iv = os.urandom(4) # reset the IV to change it, but leave .key alone. 
    file.seek(0)
    header.write(file, new_passw)

