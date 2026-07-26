/*
 * PCM ring buffer + optional macOS AudioQueue player with a pure-C callback
 * (no Python / no ctypes on the audio thread).
 */

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <string.h>
#include <stdint.h>

#ifdef __APPLE__
#include <AudioToolbox/AudioToolbox.h>
#endif

/* --- ring (device-interleaved float32) ---------------------------------- */

typedef struct {
    float *data;
    size_t capacity_frames;
    size_t channels; /* 1 or 2 */
    size_t r;        /* read index in frames */
    size_t w;        /* write index in frames */
    size_t count;    /* frames available */
    unsigned long underruns;
    PyThread_type_lock lock;
} RwtPcmRing;

static int
ring_init(RwtPcmRing *ring, size_t capacity_frames, size_t channels)
{
    memset(ring, 0, sizeof(*ring));
    if (capacity_frames < 8)
        capacity_frames = 8;
    if (channels < 1 || channels > 2) {
        PyErr_SetString(PyExc_ValueError, "channels must be 1 or 2");
        return -1;
    }
    ring->capacity_frames = capacity_frames;
    ring->channels = channels;
    ring->data = (float *)PyMem_Calloc(capacity_frames * channels, sizeof(float));
    if (!ring->data) {
        PyErr_NoMemory();
        return -1;
    }
    ring->lock = PyThread_allocate_lock();
    if (!ring->lock) {
        PyMem_Free(ring->data);
        ring->data = NULL;
        PyErr_NoMemory();
        return -1;
    }
    return 0;
}

static void
ring_fini(RwtPcmRing *ring)
{
    if (ring->data) {
        PyMem_Free(ring->data);
        ring->data = NULL;
    }
    if (ring->lock) {
        PyThread_free_lock(ring->lock);
        ring->lock = NULL;
    }
}

/* Pull interleaved device frames into out. Silence on underrun. No Python. */
static void
ring_pull_frames(RwtPcmRing *ring, float *out, size_t n_frames)
{
    size_t i, c, ch = ring->channels;
    float *dst = out;

    PyThread_acquire_lock(ring->lock, WAIT_LOCK);
    for (i = 0; i < n_frames; i++) {
        if (ring->count > 0) {
            size_t base = ring->r * ch;
            for (c = 0; c < ch; c++)
                dst[c] = ring->data[base + c];
            ring->r = (ring->r + 1) % ring->capacity_frames;
            ring->count--;
        } else {
            for (c = 0; c < ch; c++)
                dst[c] = 0.0f;
            ring->underruns++;
        }
        dst += ch;
    }
    PyThread_release_lock(ring->lock);
}

/* Push interleaved frames matching ring->channels. Returns frames written. */
static size_t
ring_push_interleaved(RwtPcmRing *ring, const float *src, size_t n_frames)
{
    size_t i, c, ch = ring->channels, pushed = 0;

    PyThread_acquire_lock(ring->lock, WAIT_LOCK);
    for (i = 0; i < n_frames; i++) {
        if (ring->count >= ring->capacity_frames)
            break;
        {
            size_t base = ring->w * ch;
            for (c = 0; c < ch; c++)
                ring->data[base + c] = src[i * ch + c];
        }
        ring->w = (ring->w + 1) % ring->capacity_frames;
        ring->count++;
        pushed++;
    }
    PyThread_release_lock(ring->lock);
    return pushed;
}

/* Push mono samples, upmixing to ring channels. */
static size_t
ring_push_mono(RwtPcmRing *ring, const float *mono, size_t n_frames)
{
    size_t i, c, ch = ring->channels, pushed = 0;

    PyThread_acquire_lock(ring->lock, WAIT_LOCK);
    for (i = 0; i < n_frames; i++) {
        if (ring->count >= ring->capacity_frames)
            break;
        {
            size_t base = ring->w * ch;
            float s = mono[i];
            for (c = 0; c < ch; c++)
                ring->data[base + c] = s;
        }
        ring->w = (ring->w + 1) % ring->capacity_frames;
        ring->count++;
        pushed++;
    }
    PyThread_release_lock(ring->lock);
    return pushed;
}

/* --- Python PcmRing type ------------------------------------------------ */

typedef struct {
    PyObject_HEAD
    RwtPcmRing ring;
    int sample_rate;
} PcmRingObject;

static int
PcmRing_init(PcmRingObject *self, PyObject *args, PyObject *kw)
{
    static char *kwlist[] = {
        "sample_rate", "channels", "latency_ms", "capacity_frames", NULL
    };
    int sample_rate = 44100;
    int channels = 2;
    double latency_ms = 25.0;
    Py_ssize_t capacity_frames = 0;

    if (!PyArg_ParseTupleAndKeywords(args, kw, "|iidn", kwlist,
                                     &sample_rate, &channels, &latency_ms,
                                     &capacity_frames))
        return -1;
    if (sample_rate <= 0) {
        PyErr_SetString(PyExc_ValueError, "sample_rate must be positive");
        return -1;
    }
    if (capacity_frames <= 0) {
        if (latency_ms <= 0.0)
            latency_ms = 25.0;
        capacity_frames = (Py_ssize_t)(sample_rate * (latency_ms / 1000.0));
        /* Comfortable minimum when sizing from latency_ms only. */
        if (capacity_frames < 256)
            capacity_frames = 256;
    }
    self->sample_rate = sample_rate;
    if (ring_init(&self->ring, (size_t)capacity_frames, (size_t)channels) < 0)
        return -1;
    return 0;
}

static void
PcmRing_dealloc(PcmRingObject *self)
{
    ring_fini(&self->ring);
    Py_TYPE(self)->tp_free((PyObject *)self);
}

static PyObject *
PcmRing_push(PcmRingObject *self, PyObject *args)
{
    Py_buffer view;
    size_t frames, pushed;
    size_t ch = self->ring.channels;

    if (!PyArg_ParseTuple(args, "y*", &view))
        return NULL;
    if (view.len % (Py_ssize_t)(ch * sizeof(float)) != 0) {
        PyBuffer_Release(&view);
        PyErr_SetString(PyExc_ValueError,
                        "buffer length must be multiple of channels*4 (float32)");
        return NULL;
    }
    frames = (size_t)view.len / (ch * sizeof(float));
    pushed = ring_push_interleaved(&self->ring, (const float *)view.buf, frames);
    PyBuffer_Release(&view);
    return PyLong_FromSize_t(pushed);
}

static PyObject *
PcmRing_push_mono(PcmRingObject *self, PyObject *args)
{
    Py_buffer view;
    size_t frames, pushed;

    if (!PyArg_ParseTuple(args, "y*", &view))
        return NULL;
    if (view.len % (Py_ssize_t)sizeof(float) != 0) {
        PyBuffer_Release(&view);
        PyErr_SetString(PyExc_ValueError,
                        "buffer length must be multiple of 4 (float32 mono)");
        return NULL;
    }
    frames = (size_t)view.len / sizeof(float);
    pushed = ring_push_mono(&self->ring, (const float *)view.buf, frames);
    PyBuffer_Release(&view);
    return PyLong_FromSize_t(pushed);
}

static PyObject *
PcmRing_pull(PcmRingObject *self, PyObject *args)
{
    /* For tests: pull into a writable buffer */
    Py_buffer view;
    size_t frames;
    size_t ch = self->ring.channels;

    if (!PyArg_ParseTuple(args, "w*", &view))
        return NULL;
    if (view.len % (Py_ssize_t)(ch * sizeof(float)) != 0) {
        PyBuffer_Release(&view);
        PyErr_SetString(PyExc_ValueError,
                        "buffer length must be multiple of channels*4");
        return NULL;
    }
    frames = (size_t)view.len / (ch * sizeof(float));
    ring_pull_frames(&self->ring, (float *)view.buf, frames);
    PyBuffer_Release(&view);
    Py_RETURN_NONE;
}

static PyObject *
PcmRing_clear(PcmRingObject *self, PyObject *Py_UNUSED(ignored))
{
    PyThread_acquire_lock(self->ring.lock, WAIT_LOCK);
    self->ring.r = self->ring.w = self->ring.count = 0;
    PyThread_release_lock(self->ring.lock);
    Py_RETURN_NONE;
}

static PyObject *
PcmRing_get_available(PcmRingObject *self, void *Py_UNUSED(c))
{
    size_t n;
    PyThread_acquire_lock(self->ring.lock, WAIT_LOCK);
    n = self->ring.count;
    PyThread_release_lock(self->ring.lock);
    return PyLong_FromSize_t(n);
}

static PyObject *
PcmRing_get_capacity(PcmRingObject *self, void *Py_UNUSED(c))
{
    return PyLong_FromSize_t(self->ring.capacity_frames);
}

static PyObject *
PcmRing_get_channels(PcmRingObject *self, void *Py_UNUSED(c))
{
    return PyLong_FromSize_t(self->ring.channels);
}

static PyObject *
PcmRing_get_sample_rate(PcmRingObject *self, void *Py_UNUSED(c))
{
    return PyLong_FromLong(self->sample_rate);
}

static PyObject *
PcmRing_get_underruns(PcmRingObject *self, void *Py_UNUSED(c))
{
    return PyLong_FromUnsignedLong(self->ring.underruns);
}

static PyObject *
PcmRing_get_latency_ms(PcmRingObject *self, void *Py_UNUSED(c))
{
    double ms = 1000.0 * (double)self->ring.capacity_frames /
                (double)self->sample_rate;
    return PyFloat_FromDouble(ms);
}

static PyGetSetDef PcmRing_getset[] = {
    {"available", (getter)PcmRing_get_available, NULL,
     "Frames currently in the ring", NULL},
    {"capacity", (getter)PcmRing_get_capacity, NULL,
     "Ring capacity in frames", NULL},
    {"channels", (getter)PcmRing_get_channels, NULL, NULL, NULL},
    {"sample_rate", (getter)PcmRing_get_sample_rate, NULL, NULL, NULL},
    {"underruns", (getter)PcmRing_get_underruns, NULL,
     "Number of frames filled with silence due to underrun", NULL},
    {"latency_ms", (getter)PcmRing_get_latency_ms, NULL,
     "Capacity expressed as milliseconds at sample_rate", NULL},
    {NULL}
};

static PyMethodDef PcmRing_methods[] = {
    {"push", (PyCFunction)PcmRing_push, METH_VARARGS,
     "push(interleaved_float32_bytes) -> frames_written"},
    {"push_mono", (PyCFunction)PcmRing_push_mono, METH_VARARGS,
     "push_mono(mono_float32_bytes) -> frames_written (upmix to ring channels)"},
    {"pull", (PyCFunction)PcmRing_pull, METH_VARARGS,
     "pull(writable_float32) — for tests; underrun fills zeros"},
    {"clear", (PyCFunction)PcmRing_clear, METH_NOARGS, "Drop all queued frames"},
    {NULL}
};

static PyTypeObject PcmRingType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "rwt_rconsole._pcm.PcmRing",
    .tp_basicsize = sizeof(PcmRingObject),
    .tp_dealloc = (destructor)PcmRing_dealloc,
    .tp_flags = Py_TPFLAGS_DEFAULT,
    .tp_doc =
        "SPSC-friendly float32 PCM ring (device channel layout).\n"
        "Default capacity ≈ latency_ms at sample_rate (default 25 ms).",
    .tp_methods = PcmRing_methods,
    .tp_getset = PcmRing_getset,
    .tp_init = (initproc)PcmRing_init,
    .tp_new = PyType_GenericNew,
};

/* --- macOS AudioQueue ring player (pure C callback) --------------------- */

#ifdef __APPLE__

#define RWT_MAX_AQ_BUFFERS 8

typedef struct {
    PyObject_HEAD
    PcmRingObject *ring_obj; /* owned ref */
    RwtPcmRing *ring;        /* alias &ring_obj->ring */
    AudioQueueRef queue;
    AudioQueueBufferRef buffers[RWT_MAX_AQ_BUFFERS];
    int buffer_count;
    int frames_per_buffer;
    int channels;
    double sample_rate;
    volatile int playing;
    volatile int disposed;
    unsigned long underruns_at_start;
} RingPlayerObject;

static void
aq_output_callback(void *user_data, AudioQueueRef aq, AudioQueueBufferRef buf)
{
    RingPlayerObject *self = (RingPlayerObject *)user_data;
    size_t n_frames;
    float *out;

    if (!self || self->disposed || !self->playing) {
        /* still re-enqueue silence if queue is running */
        if (buf && buf->mAudioData) {
            memset(buf->mAudioData, 0, buf->mAudioDataBytesCapacity);
            buf->mAudioDataByteSize = buf->mAudioDataBytesCapacity;
            AudioQueueEnqueueBuffer(aq, buf, 0, NULL);
        }
        return;
    }

    n_frames = (size_t)self->frames_per_buffer;
    out = (float *)buf->mAudioData;
    ring_pull_frames(self->ring, out, n_frames);
    buf->mAudioDataByteSize =
        (UInt32)(n_frames * (size_t)self->channels * sizeof(float));
    AudioQueueEnqueueBuffer(aq, buf, 0, NULL);
}

static int
RingPlayer_init(RingPlayerObject *self, PyObject *args, PyObject *kw)
{
    static char *kwlist[] = {
        "ring", "sample_rate", "channels",
        "frames_per_buffer", "buffer_count", NULL
    };
    PyObject *ring_obj = NULL;
    int sample_rate = 44100;
    int channels = 2;
    int frames_per_buffer = 256;
    int buffer_count = 3;
    AudioStreamBasicDescription desc;
    OSStatus st;
    int i;
    UInt32 buf_bytes;

    if (!PyArg_ParseTupleAndKeywords(args, kw, "O|iiii", kwlist,
                                     &ring_obj, &sample_rate, &channels,
                                     &frames_per_buffer, &buffer_count))
        return -1;

    if (!PyObject_TypeCheck(ring_obj, &PcmRingType)) {
        PyErr_SetString(PyExc_TypeError, "ring must be a PcmRing");
        return -1;
    }
    if (sample_rate <= 0 || channels < 1 || channels > 2) {
        PyErr_SetString(PyExc_ValueError, "invalid sample_rate or channels");
        return -1;
    }
    if (frames_per_buffer < 32)
        frames_per_buffer = 32;
    if (buffer_count < 2)
        buffer_count = 2;
    if (buffer_count > RWT_MAX_AQ_BUFFERS)
        buffer_count = RWT_MAX_AQ_BUFFERS;

    if ((size_t)channels != ((PcmRingObject *)ring_obj)->ring.channels) {
        PyErr_SetString(PyExc_ValueError,
                        "ring.channels must match player channels");
        return -1;
    }

    Py_INCREF(ring_obj);
    self->ring_obj = (PcmRingObject *)ring_obj;
    self->ring = &self->ring_obj->ring;
    self->sample_rate = (double)sample_rate;
    self->channels = channels;
    self->frames_per_buffer = frames_per_buffer;
    self->buffer_count = buffer_count;
    self->playing = 0;
    self->disposed = 0;
    self->queue = NULL;
    for (i = 0; i < RWT_MAX_AQ_BUFFERS; i++)
        self->buffers[i] = NULL;

    memset(&desc, 0, sizeof(desc));
    desc.mSampleRate = self->sample_rate;
    desc.mFormatID = kAudioFormatLinearPCM;
    desc.mFormatFlags = kAudioFormatFlagsNativeFloatPacked;
    desc.mBytesPerPacket = (UInt32)(channels * sizeof(float));
    desc.mFramesPerPacket = 1;
    desc.mBytesPerFrame = desc.mBytesPerPacket;
    desc.mChannelsPerFrame = (UInt32)channels;
    desc.mBitsPerChannel = 32;

    st = AudioQueueNewOutput(
        &desc,
        aq_output_callback,
        self, /* user data: C object, callback never touches Python */
        NULL, /* run loop NULL => AudioQueue internal thread */
        NULL,
        0,
        &self->queue);
    if (st != noErr) {
        Py_CLEAR(self->ring_obj);
        PyErr_Format(PyExc_RuntimeError,
                     "AudioQueueNewOutput failed (%d)", (int)st);
        return -1;
    }

    buf_bytes = (UInt32)(frames_per_buffer * channels * (int)sizeof(float));
    for (i = 0; i < buffer_count; i++) {
        st = AudioQueueAllocateBuffer(self->queue, buf_bytes, &self->buffers[i]);
        if (st != noErr) {
            PyErr_Format(PyExc_RuntimeError,
                         "AudioQueueAllocateBuffer failed (%d)", (int)st);
            return -1;
        }
    }
    return 0;
}

static void
RingPlayer_stop_internal(RingPlayerObject *self)
{
    int i;
    self->playing = 0;
    if (self->queue) {
        AudioQueueStop(self->queue, true);
        AudioQueueReset(self->queue);
        for (i = 0; i < self->buffer_count; i++) {
            if (self->buffers[i]) {
                /* buffers freed with queue dispose */
                self->buffers[i] = NULL;
            }
        }
        AudioQueueDispose(self->queue, true);
        self->queue = NULL;
    }
}

static void
RingPlayer_dealloc(RingPlayerObject *self)
{
    self->disposed = 1;
    self->playing = 0;
    if (self->queue) {
        AudioQueueStop(self->queue, true);
        AudioQueueDispose(self->queue, true);
        self->queue = NULL;
    }
    Py_CLEAR(self->ring_obj);
    Py_TYPE(self)->tp_free((PyObject *)self);
}

static PyObject *
RingPlayer_play(RingPlayerObject *self, PyObject *Py_UNUSED(ignored))
{
    int i;
    OSStatus st;
    size_t n_frames;
    float *out;

    if (self->disposed || !self->queue) {
        PyErr_SetString(PyExc_RuntimeError, "RingPlayer is closed");
        return NULL;
    }
    if (self->playing)
        Py_RETURN_NONE;

    self->playing = 1;
    n_frames = (size_t)self->frames_per_buffer;
    /* prime buffers */
    for (i = 0; i < self->buffer_count; i++) {
        if (!self->buffers[i])
            continue;
        out = (float *)self->buffers[i]->mAudioData;
        ring_pull_frames(self->ring, out, n_frames);
        self->buffers[i]->mAudioDataByteSize =
            (UInt32)(n_frames * (size_t)self->channels * sizeof(float));
        st = AudioQueueEnqueueBuffer(self->queue, self->buffers[i], 0, NULL);
        if (st != noErr) {
            self->playing = 0;
            PyErr_Format(PyExc_RuntimeError,
                         "AudioQueueEnqueueBuffer failed (%d)", (int)st);
            return NULL;
        }
    }
    st = AudioQueueStart(self->queue, NULL);
    if (st != noErr) {
        self->playing = 0;
        PyErr_Format(PyExc_RuntimeError, "AudioQueueStart failed (%d)", (int)st);
        return NULL;
    }
    Py_RETURN_NONE;
}

static PyObject *
RingPlayer_pause(RingPlayerObject *self, PyObject *Py_UNUSED(ignored))
{
    if (self->queue && self->playing) {
        self->playing = 0;
        AudioQueuePause(self->queue);
    }
    Py_RETURN_NONE;
}

static PyObject *
RingPlayer_stop(RingPlayerObject *self, PyObject *Py_UNUSED(ignored))
{
    if (self->queue) {
        self->playing = 0;
        AudioQueueStop(self->queue, true);
        AudioQueueReset(self->queue);
    }
    Py_RETURN_NONE;
}

static PyObject *
RingPlayer_close(RingPlayerObject *self, PyObject *Py_UNUSED(ignored))
{
    self->disposed = 1;
    self->playing = 0;
    if (self->queue) {
        AudioQueueStop(self->queue, true);
        AudioQueueDispose(self->queue, true);
        self->queue = NULL;
    }
    Py_CLEAR(self->ring_obj);
    Py_RETURN_NONE;
}

static PyObject *
RingPlayer_enter(RingPlayerObject *self, PyObject *Py_UNUSED(ignored))
{
    Py_INCREF(self);
    return (PyObject *)self;
}

static PyObject *
RingPlayer_exit(RingPlayerObject *self, PyObject *Py_UNUSED(args))
{
    return RingPlayer_close(self, NULL);
}

static PyObject *
RingPlayer_get_playing(RingPlayerObject *self, void *Py_UNUSED(c))
{
    return PyBool_FromLong(self->playing);
}

static PyObject *
RingPlayer_get_frames_per_buffer(RingPlayerObject *self, void *Py_UNUSED(c))
{
    return PyLong_FromLong(self->frames_per_buffer);
}

static PyObject *
RingPlayer_get_buffer_count(RingPlayerObject *self, void *Py_UNUSED(c))
{
    return PyLong_FromLong(self->buffer_count);
}

static PyObject *
RingPlayer_get_device_latency_ms(RingPlayerObject *self, void *Py_UNUSED(c))
{
    /* Approximate queued AQ latency: buffer_count * frames_per_buffer */
    double frames = (double)self->buffer_count * (double)self->frames_per_buffer;
    double ms = 1000.0 * frames / self->sample_rate;
    return PyFloat_FromDouble(ms);
}

static PyGetSetDef RingPlayer_getset[] = {
    {"playing", (getter)RingPlayer_get_playing, NULL, NULL, NULL},
    {"frames_per_buffer", (getter)RingPlayer_get_frames_per_buffer, NULL,
     "AudioQueue buffer size in frames (tunable; not fixed by the OS)", NULL},
    {"buffer_count", (getter)RingPlayer_get_buffer_count, NULL,
     "Number of AudioQueue buffers (tunable; not fixed by the OS)", NULL},
    {"device_latency_ms", (getter)RingPlayer_get_device_latency_ms, NULL,
     "Approx AQ pipeline depth: buffer_count * frames_per_buffer", NULL},
    {NULL}
};

static PyMethodDef RingPlayer_methods[] = {
    {"play", (PyCFunction)RingPlayer_play, METH_NOARGS, NULL},
    {"pause", (PyCFunction)RingPlayer_pause, METH_NOARGS, NULL},
    {"stop", (PyCFunction)RingPlayer_stop, METH_NOARGS, NULL},
    {"close", (PyCFunction)RingPlayer_close, METH_NOARGS, NULL},
    {"__enter__", (PyCFunction)RingPlayer_enter, METH_NOARGS, NULL},
    {"__exit__", (PyCFunction)RingPlayer_exit, METH_VARARGS, NULL},
    {NULL}
};

static PyTypeObject RingPlayerType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "rwt_rconsole._pcm.RingPlayer",
    .tp_basicsize = sizeof(RingPlayerObject),
    .tp_dealloc = (destructor)RingPlayer_dealloc,
    .tp_flags = Py_TPFLAGS_DEFAULT,
    .tp_doc =
        "macOS AudioQueue player that drains a PcmRing from a pure-C callback "
        "(no GIL on the audio thread).\n"
        "frames_per_buffer and buffer_count are fully tunable; Apple does not "
        "require 3×512.",
    .tp_methods = RingPlayer_methods,
    .tp_getset = RingPlayer_getset,
    .tp_init = (initproc)RingPlayer_init,
    .tp_new = PyType_GenericNew,
};

#endif /* __APPLE__ */

/* --- module ------------------------------------------------------------- */

static struct PyModuleDef moduledef = {
    PyModuleDef_HEAD_INIT,
    .m_name = "_pcm",
    .m_doc = "PCM ring and optional pure-C AudioQueue ring player.",
    .m_size = -1,
};

PyMODINIT_FUNC
PyInit__pcm(void)
{
    PyObject *m;

    if (PyType_Ready(&PcmRingType) < 0)
        return NULL;
#ifdef __APPLE__
    if (PyType_Ready(&RingPlayerType) < 0)
        return NULL;
#endif

    m = PyModule_Create(&moduledef);
    if (!m)
        return NULL;

    Py_INCREF(&PcmRingType);
    if (PyModule_AddObject(m, "PcmRing", (PyObject *)&PcmRingType) < 0) {
        Py_DECREF(&PcmRingType);
        Py_DECREF(m);
        return NULL;
    }

#ifdef __APPLE__
    Py_INCREF(&RingPlayerType);
    if (PyModule_AddObject(m, "RingPlayer", (PyObject *)&RingPlayerType) < 0) {
        Py_DECREF(&RingPlayerType);
        Py_DECREF(m);
        return NULL;
    }
    PyModule_AddIntConstant(m, "HAS_RING_PLAYER", 1);
#else
    PyModule_AddIntConstant(m, "HAS_RING_PLAYER", 0);
#endif

    PyModule_AddIntConstant(m, "DEFAULT_LATENCY_MS", 25);
    PyModule_AddIntConstant(m, "DEFAULT_FRAMES_PER_BUFFER", 256);
    PyModule_AddIntConstant(m, "DEFAULT_BUFFER_COUNT", 3);

    return m;
}
