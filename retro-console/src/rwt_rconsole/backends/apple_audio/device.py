"""Apple AudioQueue-backed streaming audio for macOS."""

from __future__ import annotations

import ctypes
import sys
import threading
from ctypes import (
    CFUNCTYPE,
    POINTER,
    Structure,
    byref,
    c_byte,
    c_double,
    c_float,
    c_int,
    c_uint32,
    c_void_p,
    cast,
)

from rwt_rconsole.audio import (
    AudioCallback,
    AudioConfig,
    AudioPlaybackState,
    AudioSampleFormat,
    as_int16,
    as_int8,
    sample_size,
)

if sys.platform != "darwin":
    raise ImportError("Apple Audio backend is only available on macOS")

_AudioToolbox = ctypes.CDLL(
    "/System/Library/Frameworks/AudioToolbox.framework/AudioToolbox"
)

kAudioFormatLinearPCM = 0x6C70636D  # 'lpcm'
kAudioFormatFlagsNativeFloatPacked = 0x00000009


class AudioStreamBasicDescription(Structure):
    _fields_ = [
        ("mSampleRate", c_double),
        ("mFormatID", c_uint32),
        ("mFormatFlags", c_uint32),
        ("mBytesPerPacket", c_uint32),
        ("mFramesPerPacket", c_uint32),
        ("mBytesPerFrame", c_uint32),
        ("mChannelsPerFrame", c_uint32),
        ("mBitsPerChannel", c_uint32),
        ("mReserved", c_uint32),
    ]


class AudioQueueBuffer(Structure):
    _fields_ = [
        ("mAudioDataBytesCapacity", c_uint32),
        ("mAudioData", c_void_p),
        ("mAudioDataByteSize", c_uint32),
        ("mUserData", c_void_p),
        ("mPacketDescriptionCapacity", c_uint32),
        ("mPacketDescriptions", c_void_p),
        ("mNumberPacketDescriptions", c_uint32),
    ]


AudioQueueOutputCallback = CFUNCTYPE(None, c_void_p, c_void_p, c_void_p)

_AudioToolbox.AudioQueueNewOutput.argtypes = [
    POINTER(AudioStreamBasicDescription),
    AudioQueueOutputCallback,
    c_void_p,
    c_void_p,
    c_void_p,
    c_uint32,
    POINTER(c_void_p),
]
_AudioToolbox.AudioQueueNewOutput.restype = c_int

_AudioToolbox.AudioQueueAllocateBuffer.argtypes = [c_void_p, c_uint32, POINTER(c_void_p)]
_AudioToolbox.AudioQueueAllocateBuffer.restype = c_int

_AudioToolbox.AudioQueueEnqueueBuffer.argtypes = [c_void_p, c_void_p, c_uint32, c_void_p]
_AudioToolbox.AudioQueueEnqueueBuffer.restype = c_int

_AudioToolbox.AudioQueueStart.argtypes = [c_void_p, c_void_p]
_AudioToolbox.AudioQueueStart.restype = c_int

_AudioToolbox.AudioQueuePause.argtypes = [c_void_p]
_AudioToolbox.AudioQueuePause.restype = c_int

_AudioToolbox.AudioQueueStop.argtypes = [c_void_p, c_byte]
_AudioToolbox.AudioQueueStop.restype = c_int

_AudioToolbox.AudioQueueReset.argtypes = [c_void_p]
_AudioToolbox.AudioQueueReset.restype = c_int

_AudioToolbox.AudioQueueDispose.argtypes = [c_void_p, c_byte]
_AudioToolbox.AudioQueueDispose.restype = c_int


def _check_err(action: str, status: int) -> None:
    if status != 0:
        raise RuntimeError(f"{action} failed with status {status} (0x{status:X})")


class AppleAudio:
    """Apple AudioQueue streaming device with optional software reverb."""

    def __init__(self, config: AudioConfig, callback: AudioCallback) -> None:
        self._config = config
        self._callback = callback
        self._lock = threading.Lock()
        self._state = AudioPlaybackState.STOPPED
        self._reverb = config.reverb
        self._last_error: BaseException | None = None
        self._disposed = False
        self._playing = False

        num_channels = int(config.channels)
        self._num_channels = num_channels
        bytes_per_frame_float = num_channels * 4
        self._frames_per_buffer = 512
        self._buffer_byte_size = self._frames_per_buffer * bytes_per_frame_float
        buffer_count = 3

        delay_length = int(config.sample_rate * 0.054) * num_channels
        self._delay_buffer = [0.0] * max(delay_length, 1)
        self._delay_pos = 0

        self._scratch = bytearray()
        self._queue = c_void_p()
        self._buffer_ptrs: list[c_void_p] = []

        # Keep callback alive for the lifetime of the queue.
        self._c_callback = AudioQueueOutputCallback(self._on_output)

        stream_desc = AudioStreamBasicDescription(
            mSampleRate=float(config.sample_rate),
            mFormatID=kAudioFormatLinearPCM,
            mFormatFlags=kAudioFormatFlagsNativeFloatPacked,
            mBytesPerPacket=bytes_per_frame_float,
            mFramesPerPacket=1,
            mBytesPerFrame=bytes_per_frame_float,
            mChannelsPerFrame=num_channels,
            mBitsPerChannel=32,
            mReserved=0,
        )
        status = _AudioToolbox.AudioQueueNewOutput(
            byref(stream_desc),
            self._c_callback,
            None,
            None,
            None,
            0,
            byref(self._queue),
        )
        _check_err("AudioQueueNewOutput", status)

        for _ in range(buffer_count):
            buf_ptr = c_void_p()
            status = _AudioToolbox.AudioQueueAllocateBuffer(
                self._queue, self._buffer_byte_size, byref(buf_ptr)
            )
            _check_err("AudioQueueAllocateBuffer", status)
            self._buffer_ptrs.append(buf_ptr)

    def _fill_buffer(self, buf_ptr: int) -> None:
        if not self._playing or not buf_ptr:
            return
        native_buf = cast(buf_ptr, POINTER(AudioQueueBuffer)).contents
        out_ptr = native_buf.mAudioData
        if not out_ptr:
            return

        num_samples = self._frames_per_buffer * self._num_channels
        out_floats = (c_float * num_samples).from_address(out_ptr)

        try:
            cfg = self._config
            if cfg.format is AudioSampleFormat.FLOAT32:
                byte_view = memoryview(
                    (ctypes.c_uint8 * self._buffer_byte_size).from_address(out_ptr)
                )
                self._callback(byte_view)
            else:
                client_bytes = self._frames_per_buffer * self._num_channels * sample_size(
                    cfg.format
                )
                if len(self._scratch) < client_bytes:
                    self._scratch = bytearray(client_bytes)
                client_mv = memoryview(self._scratch)[:client_bytes]
                self._callback(client_mv)

                if cfg.format is AudioSampleFormat.INT16:
                    src = as_int16(client_mv)
                    for i in range(num_samples):
                        out_floats[i] = src[i] / 32768.0
                elif cfg.format is AudioSampleFormat.INT8:
                    src = as_int8(client_mv)
                    for i in range(num_samples):
                        out_floats[i] = src[i] / 128.0
                elif cfg.format is AudioSampleFormat.UINT8:
                    for i in range(num_samples):
                        out_floats[i] = (client_mv[i] - 128) / 128.0

            level = self._reverb
            if level > 0:
                # Apply reverb in-place via ctypes array indexing
                feedback = (level / 255.0) * 0.55
                damp = feedback * 0.45
                delay = self._delay_buffer
                n = len(delay)
                pos = self._delay_pos
                for i in range(num_samples):
                    dry = float(out_floats[i])
                    delayed = delay[pos]
                    wet = dry + delayed * feedback
                    out_floats[i] = max(-1.0, min(1.0, wet))
                    delay[pos] = dry + delayed * damp
                    pos = (pos + 1) % n
                self._delay_pos = pos

            native_buf.mAudioDataByteSize = self._buffer_byte_size
            _AudioToolbox.AudioQueueEnqueueBuffer(self._queue, buf_ptr, 0, None)
        except BaseException as ex:
            self._playing = False
            with self._lock:
                self._last_error = ex
                self._state = AudioPlaybackState.STOPPED
            for i in range(num_samples):
                out_floats[i] = 0.0

    def _on_output(self, _user: int, _aq: int, buf_ptr: int) -> None:
        self._fill_buffer(buf_ptr)

    def _prime_buffers(self) -> None:
        for bp in self._buffer_ptrs:
            if bp.value:
                self._fill_buffer(bp.value)

    def _throw_if_disposed(self) -> None:
        if self._disposed:
            raise RuntimeError("AppleAudio is closed")

    @property
    def config(self) -> AudioConfig:
        return self._config

    @property
    def state(self) -> AudioPlaybackState:
        with self._lock:
            return self._state

    def play(self) -> None:
        self._throw_if_disposed()
        with self._lock:
            if self._state is AudioPlaybackState.PLAYING:
                return
            self._state = AudioPlaybackState.PLAYING
            self._playing = True
        self._prime_buffers()
        if _AudioToolbox.AudioQueueStart(self._queue, None) != 0:
            with self._lock:
                self._playing = False
                self._state = AudioPlaybackState.STOPPED

    def pause(self) -> None:
        self._throw_if_disposed()
        with self._lock:
            if self._state is not AudioPlaybackState.PLAYING:
                return
            self._playing = False
            self._state = AudioPlaybackState.PAUSED
        _AudioToolbox.AudioQueuePause(self._queue)

    def stop(self) -> None:
        self._throw_if_disposed()
        with self._lock:
            if self._state is AudioPlaybackState.STOPPED:
                return
            self._playing = False
            self._state = AudioPlaybackState.STOPPED
        _AudioToolbox.AudioQueueReset(self._queue)
        _AudioToolbox.AudioQueueStop(self._queue, 1)

    @property
    def has_reverb_support(self) -> bool:
        return True

    @property
    def reverb(self) -> int:
        with self._lock:
            return self._reverb

    @reverb.setter
    def reverb(self, value: int) -> None:
        self._throw_if_disposed()
        if not 0 <= value <= 255:
            raise ValueError("Reverb must be 0..255")
        with self._lock:
            self._reverb = value

    @property
    def last_error(self) -> BaseException | None:
        with self._lock:
            return self._last_error

    def close(self) -> None:
        with self._lock:
            if self._disposed:
                return
            self._disposed = True
            self._playing = False
            self._state = AudioPlaybackState.STOPPED
            q = self._queue
            self._queue = c_void_p()
        if q.value:
            _AudioToolbox.AudioQueueReset(q)
            _AudioToolbox.AudioQueueStop(q, 1)
            _AudioToolbox.AudioQueueDispose(q, 1)

    def __enter__(self) -> AppleAudio:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


# Back-compat alias
AppleRetroAudio = AppleAudio
