/*
 * Retro sound-chip cores: PC Speaker and SN76489-family (Tandy / Sega).
 *
 * Pure synthesis: register control + render float32 mono PCM.
 * Host audio rings / device pull live in rwt_rconsole, not here.
 * NES APU is in _nes_apu.c.
 */

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <math.h>
#include <stdint.h>
#include <string.h>

int rwt_nes_apu_add_to_module(PyObject *m);

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

/* --- shared waveform helpers -------------------------------------------- */

enum {
    RWT_WAVE_SQUARE = 0,
    RWT_WAVE_TRIANGLE = 1,
    RWT_WAVE_SAWTOOTH = 2,
    RWT_WAVE_SINE = 3,
};

static inline float
waveform_sample(int wave, double phase)
{
    switch (wave) {
    case RWT_WAVE_TRIANGLE:
        if (phase < 0.5)
            return (float)(phase * 4.0 - 1.0);
        return (float)(3.0 - phase * 4.0);
    case RWT_WAVE_SAWTOOTH:
        return (float)(phase * 2.0 - 1.0);
    case RWT_WAVE_SINE:
        return (float)sin(phase * 2.0 * M_PI);
    case RWT_WAVE_SQUARE:
    default:
        return phase < 0.5f ? 1.0f : -1.0f;
    }
}

static int
parse_waveform(int wave)
{
    if (wave < RWT_WAVE_SQUARE || wave > RWT_WAVE_SINE) {
        PyErr_Format(PyExc_ValueError, "waveform must be 0..3, got %d", wave);
        return -1;
    }
    return 0;
}

static int
parse_float_buf(PyObject *args, Py_buffer *view, float **out, Py_ssize_t *n)
{
    if (!PyArg_ParseTuple(args, "w*", view))
        return -1;
    if (view->len % (Py_ssize_t)sizeof(float) != 0) {
        PyBuffer_Release(view);
        PyErr_SetString(PyExc_ValueError,
                        "buffer length must be a multiple of 4 (float32)");
        return -1;
    }
    if (view->readonly) {
        PyBuffer_Release(view);
        PyErr_SetString(PyExc_BufferError, "buffer must be writable");
        return -1;
    }
    *out = (float *)view->buf;
    *n = view->len / (Py_ssize_t)sizeof(float);
    return 0;
}

/* --- volume table for SN76489 (approx -2 dB steps; 15 = mute) ----------- */

static float sn_vol_table[16];
static int sn_vol_ready = 0;

static void
init_sn_vol_table(void)
{
    int i;
    if (sn_vol_ready)
        return;
    for (i = 0; i < 15; i++)
        sn_vol_table[i] = (float)pow(10.0, -0.1 * (double)i);
    sn_vol_table[15] = 0.0f;
    sn_vol_ready = 1;
}

/* ========================================================================
 * PC Speaker
 * ======================================================================== */

#define PIT_CLOCK_HZ 1193182.0

typedef struct {
    PyObject_HEAD
    double sample_rate;
    double phase;
    double freq_hz;
    int gate;
    int waveform;
    float amplitude;
} PCSpeakerObject;

static float
pcs_mix_one(PCSpeakerObject *self)
{
    float s = 0.0f;
    double phase_inc;
    if (self->gate && self->freq_hz > 0.0) {
        s = waveform_sample(self->waveform, self->phase) * self->amplitude;
        phase_inc = self->freq_hz / self->sample_rate;
        self->phase += phase_inc;
        if (self->phase >= 1.0)
            self->phase -= floor(self->phase);
    }
    return s;
}

static int
pcs_init(PCSpeakerObject *self, PyObject *args, PyObject *kw)
{
    static char *kwlist[] = {"sample_rate", "amplitude", NULL};
    double sr = 44100.0;
    double amp = 0.25;
    if (!PyArg_ParseTupleAndKeywords(args, kw, "|dd", kwlist, &sr, &amp))
        return -1;
    if (sr <= 0.0) {
        PyErr_SetString(PyExc_ValueError, "sample_rate must be positive");
        return -1;
    }
    if (amp < 0.0 || amp > 1.0) {
        PyErr_SetString(PyExc_ValueError, "amplitude must be 0..1");
        return -1;
    }
    self->sample_rate = sr;
    self->phase = 0.0;
    self->freq_hz = 0.0;
    self->gate = 0;
    self->waveform = RWT_WAVE_SQUARE;
    self->amplitude = (float)amp;
    return 0;
}

static PyObject *
pcs_reset(PCSpeakerObject *self, PyObject *Py_UNUSED(ignored))
{
    self->phase = 0.0;
    self->freq_hz = 0.0;
    self->gate = 0;
    self->waveform = RWT_WAVE_SQUARE;
    Py_RETURN_NONE;
}

static PyObject *
pcs_set_frequency_hz(PCSpeakerObject *self, PyObject *args)
{
    double f;
    if (!PyArg_ParseTuple(args, "d", &f))
        return NULL;
    if (f < 0.0) {
        PyErr_SetString(PyExc_ValueError, "frequency must be >= 0");
        return NULL;
    }
    self->freq_hz = f;
    Py_RETURN_NONE;
}

static PyObject *
pcs_set_pit_divisor(PCSpeakerObject *self, PyObject *args)
{
    unsigned long div;
    if (!PyArg_ParseTuple(args, "k", &div))
        return NULL;
    if (div == 0)
        self->freq_hz = 0.0;
    else
        self->freq_hz = PIT_CLOCK_HZ / (double)div;
    Py_RETURN_NONE;
}

static PyObject *
pcs_set_gate(PCSpeakerObject *self, PyObject *args)
{
    int g;
    if (!PyArg_ParseTuple(args, "p", &g))
        return NULL;
    self->gate = g ? 1 : 0;
    Py_RETURN_NONE;
}

static PyObject *
pcs_set_waveform(PCSpeakerObject *self, PyObject *args)
{
    int w;
    if (!PyArg_ParseTuple(args, "i", &w))
        return NULL;
    if (parse_waveform(w) < 0)
        return NULL;
    self->waveform = w;
    Py_RETURN_NONE;
}

static PyObject *
pcs_set_amplitude(PCSpeakerObject *self, PyObject *args)
{
    double a;
    if (!PyArg_ParseTuple(args, "d", &a))
        return NULL;
    if (a < 0.0 || a > 1.0) {
        PyErr_SetString(PyExc_ValueError, "amplitude must be 0..1");
        return NULL;
    }
    self->amplitude = (float)a;
    Py_RETURN_NONE;
}

static PyObject *
pcs_render_into(PCSpeakerObject *self, PyObject *args)
{
    Py_buffer view;
    Py_ssize_t n, i;
    float *out;

    if (parse_float_buf(args, &view, &out, &n) < 0)
        return NULL;
    for (i = 0; i < n; i++)
        out[i] = pcs_mix_one(self);
    PyBuffer_Release(&view);
    Py_RETURN_NONE;
}

static PyObject *
pcs_get_sample_rate(PCSpeakerObject *self, void *Py_UNUSED(closure))
{
    return PyFloat_FromDouble(self->sample_rate);
}

static PyObject *
pcs_get_freq(PCSpeakerObject *self, void *Py_UNUSED(closure))
{
    return PyFloat_FromDouble(self->freq_hz);
}

static PyObject *
pcs_get_gate(PCSpeakerObject *self, void *Py_UNUSED(closure))
{
    return PyBool_FromLong(self->gate);
}

static PyObject *
pcs_get_waveform(PCSpeakerObject *self, void *Py_UNUSED(closure))
{
    return PyLong_FromLong(self->waveform);
}

static PyObject *
pcs_get_amplitude(PCSpeakerObject *self, void *Py_UNUSED(closure))
{
    return PyFloat_FromDouble((double)self->amplitude);
}

static PyGetSetDef pcs_getset[] = {
    {"sample_rate", (getter)pcs_get_sample_rate, NULL, NULL, NULL},
    {"frequency_hz", (getter)pcs_get_freq, NULL, NULL, NULL},
    {"gate", (getter)pcs_get_gate, NULL, NULL, NULL},
    {"waveform", (getter)pcs_get_waveform, NULL, NULL, NULL},
    {"amplitude", (getter)pcs_get_amplitude, NULL, NULL, NULL},
    {NULL}
};

static PyMethodDef pcs_methods[] = {
    {"reset", (PyCFunction)pcs_reset, METH_NOARGS, NULL},
    {"set_frequency_hz", (PyCFunction)pcs_set_frequency_hz, METH_VARARGS, NULL},
    {"set_pit_divisor", (PyCFunction)pcs_set_pit_divisor, METH_VARARGS, NULL},
    {"set_gate", (PyCFunction)pcs_set_gate, METH_VARARGS, NULL},
    {"set_waveform", (PyCFunction)pcs_set_waveform, METH_VARARGS, NULL},
    {"set_amplitude", (PyCFunction)pcs_set_amplitude, METH_VARARGS, NULL},
    {"render_into", (PyCFunction)pcs_render_into, METH_VARARGS,
     "Render mono float32 samples into a writable buffer."},
    {NULL}
};

static PyTypeObject PCSpeakerType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "rwt_rsound._chips.PCSpeakerCore",
    .tp_basicsize = sizeof(PCSpeakerObject),
    .tp_flags = Py_TPFLAGS_DEFAULT,
    .tp_doc = "IBM PC Speaker core (PIT square wave by default).",
    .tp_methods = pcs_methods,
    .tp_getset = pcs_getset,
    .tp_init = (initproc)pcs_init,
    .tp_new = PyType_GenericNew,
};

/* ========================================================================
 * SN76489 family (Tandy SN76496 / Sega PSG)
 * ======================================================================== */

enum {
    SN_VARIANT_TANDY = 0,
    SN_VARIANT_SEGA = 1,
};

typedef struct {
    PyObject_HEAD
    int variant;
    double clock_hz;
    double sample_rate;
    float master_gain;

    uint16_t tone_period[3];
    uint8_t tone_vol[3];
    uint8_t noise_vol;
    uint8_t noise_ctrl;

    uint16_t tone_counter[3];
    uint8_t tone_out[3];
    double tone_phase[3];
    int tone_wave[3];

    uint16_t noise_counter;
    uint16_t noise_lfsr;
    uint8_t noise_out;

    int latched_reg;
    double clocks_per_sample;
    double clock_accum;
} SN76496Object;

static void
sn_reset_state(SN76496Object *self)
{
    int i;
    for (i = 0; i < 3; i++) {
        self->tone_period[i] = 0;
        self->tone_vol[i] = 0x0F;
        self->tone_counter[i] = 0;
        self->tone_out[i] = 1;
        self->tone_phase[i] = 0.0;
        self->tone_wave[i] = RWT_WAVE_SQUARE;
    }
    self->noise_vol = 0x0F;
    self->noise_ctrl = 0x00;
    self->noise_counter = 0;
    self->noise_out = 1;
    if (self->variant == SN_VARIANT_SEGA)
        self->noise_lfsr = 0x8000;
    else
        self->noise_lfsr = 1 << 14;
    self->latched_reg = 0;
    self->clock_accum = 0.0;
    self->clocks_per_sample = self->clock_hz / self->sample_rate;
}

static int
sn_init(SN76496Object *self, PyObject *args, PyObject *kw)
{
    static char *kwlist[] = {"variant", "sample_rate", "clock_hz", "master_gain", NULL};
    int variant = SN_VARIANT_TANDY;
    double sr = 44100.0;
    double clock = 0.0;
    double gain = 0.25;

    init_sn_vol_table();

    if (!PyArg_ParseTupleAndKeywords(args, kw, "|iddd", kwlist,
                                     &variant, &sr, &clock, &gain))
        return -1;
    if (variant != SN_VARIANT_TANDY && variant != SN_VARIANT_SEGA) {
        PyErr_SetString(PyExc_ValueError, "variant must be 0 (tandy) or 1 (sega)");
        return -1;
    }
    if (sr <= 0.0) {
        PyErr_SetString(PyExc_ValueError, "sample_rate must be positive");
        return -1;
    }
    if (clock <= 0.0)
        clock = 3579545.0;
    if (gain < 0.0 || gain > 1.0) {
        PyErr_SetString(PyExc_ValueError, "master_gain must be 0..1");
        return -1;
    }

    self->variant = variant;
    self->sample_rate = sr;
    self->clock_hz = clock;
    self->master_gain = (float)gain;
    sn_reset_state(self);
    return 0;
}

static PyObject *
sn_reset(SN76496Object *self, PyObject *Py_UNUSED(ignored))
{
    sn_reset_state(self);
    Py_RETURN_NONE;
}

static void
sn_write_byte(SN76496Object *self, int value)
{
    int data = value & 0xFF;
    int reg, ch;

    if (data & 0x80) {
        self->latched_reg = (data >> 4) & 0x07;
        reg = self->latched_reg;
        switch (reg) {
        case 0: case 2: case 4:
            ch = reg >> 1;
            self->tone_period[ch] =
                (uint16_t)((self->tone_period[ch] & 0x3F0) | (data & 0x0F));
            break;
        case 1: case 3: case 5:
            ch = reg >> 1;
            self->tone_vol[ch] = (uint8_t)(data & 0x0F);
            break;
        case 6:
            self->noise_ctrl = (uint8_t)(data & 0x0F);
            if (self->variant == SN_VARIANT_SEGA)
                self->noise_lfsr = 0x8000;
            else
                self->noise_lfsr = 1 << 14;
            break;
        case 7:
            self->noise_vol = (uint8_t)(data & 0x0F);
            break;
        }
    } else {
        reg = self->latched_reg;
        if (reg == 0 || reg == 2 || reg == 4) {
            ch = reg >> 1;
            self->tone_period[ch] =
                (uint16_t)((self->tone_period[ch] & 0x00F) |
                           ((data & 0x3F) << 4));
        }
    }
}

static PyObject *
sn_write(SN76496Object *self, PyObject *args)
{
    int value;
    if (PyTuple_Size(args) == 1) {
        if (!PyArg_ParseTuple(args, "i", &value))
            return NULL;
    } else {
        int addr;
        if (!PyArg_ParseTuple(args, "ii", &addr, &value))
            return NULL;
        (void)addr;
    }
    sn_write_byte(self, value);
    Py_RETURN_NONE;
}

static PyObject *
sn_set_tone(SN76496Object *self, PyObject *args, PyObject *kw)
{
    static char *kwlist[] = {"channel", "period", "volume", NULL};
    int ch, period = -1, vol = -1;
    if (!PyArg_ParseTupleAndKeywords(args, kw, "i|ii", kwlist, &ch, &period, &vol))
        return NULL;
    if (ch < 0 || ch > 2) {
        PyErr_SetString(PyExc_ValueError, "channel must be 0..2");
        return NULL;
    }
    if (period >= 0)
        self->tone_period[ch] = (uint16_t)(period & 0x3FF);
    if (vol >= 0)
        self->tone_vol[ch] = (uint8_t)(vol & 0x0F);
    Py_RETURN_NONE;
}

static PyObject *
sn_set_noise(SN76496Object *self, PyObject *args, PyObject *kw)
{
    static char *kwlist[] = {"control", "volume", NULL};
    int control = -1, vol = -1;
    if (!PyArg_ParseTupleAndKeywords(args, kw, "|ii", kwlist, &control, &vol))
        return NULL;
    if (control >= 0) {
        self->noise_ctrl = (uint8_t)(control & 0x0F);
        if (self->variant == SN_VARIANT_SEGA)
            self->noise_lfsr = 0x8000;
        else
            self->noise_lfsr = 1 << 14;
    }
    if (vol >= 0)
        self->noise_vol = (uint8_t)(vol & 0x0F);
    Py_RETURN_NONE;
}

static PyObject *
sn_set_tone_waveform(SN76496Object *self, PyObject *args)
{
    int ch, w;
    if (!PyArg_ParseTuple(args, "ii", &ch, &w))
        return NULL;
    if (ch < 0 || ch > 2) {
        PyErr_SetString(PyExc_ValueError, "channel must be 0..2");
        return NULL;
    }
    if (parse_waveform(w) < 0)
        return NULL;
    self->tone_wave[ch] = w;
    Py_RETURN_NONE;
}

static uint16_t
sn_noise_period(SN76496Object *self)
{
    switch (self->noise_ctrl & 0x03) {
    case 0: return 0x10;
    case 1: return 0x20;
    case 2: return 0x40;
    default: {
        uint16_t p = self->tone_period[2];
        return p ? p : 1;
    }
    }
}

static int
sn_lfsr_step(SN76496Object *self)
{
    int out = self->noise_lfsr & 1;
    int fb;
    if (self->variant == SN_VARIANT_SEGA) {
        fb = (self->noise_lfsr ^ (self->noise_lfsr >> 3)) & 1;
        self->noise_lfsr = (uint16_t)((self->noise_lfsr >> 1) | (fb << 15));
    } else {
        fb = (self->noise_lfsr ^ (self->noise_lfsr >> 1)) & 1;
        self->noise_lfsr = (uint16_t)(((self->noise_lfsr >> 1) | (fb << 14)) & 0x7FFF);
    }
    return out;
}

static void
sn_clock_chip(SN76496Object *self, int cycles)
{
    int ch;
    uint16_t period, nper;

    self->clock_accum += (double)cycles;
    while (self->clock_accum >= 16.0) {
        self->clock_accum -= 16.0;

        for (ch = 0; ch < 3; ch++) {
            period = self->tone_period[ch];
            if (period == 0)
                continue;
            if (self->tone_counter[ch] > 0)
                self->tone_counter[ch]--;
            if (self->tone_counter[ch] == 0) {
                self->tone_counter[ch] = period;
                self->tone_out[ch] ^= 1;
            }
        }

        nper = sn_noise_period(self);
        if (self->noise_counter > 0)
            self->noise_counter--;
        if (self->noise_counter == 0) {
            self->noise_counter = nper;
            self->noise_out = (uint8_t)sn_lfsr_step(self);
        }
    }
}

static float
sn_mix_sample(SN76496Object *self)
{
    float mix = 0.0f;
    int ch;
    float v;
    double freq, phase_inc;
    float sample;

    for (ch = 0; ch < 3; ch++) {
        v = sn_vol_table[self->tone_vol[ch] & 0x0F];
        if (v <= 0.0f)
            continue;
        if (self->tone_wave[ch] == RWT_WAVE_SQUARE || self->tone_period[ch] == 0) {
            sample = self->tone_out[ch] ? 1.0f : -1.0f;
        } else {
            if (self->tone_period[ch] == 0)
                sample = 0.0f;
            else {
                freq = self->clock_hz / (32.0 * (double)self->tone_period[ch]);
                phase_inc = freq / self->sample_rate;
                sample = waveform_sample(self->tone_wave[ch], self->tone_phase[ch]);
                self->tone_phase[ch] += phase_inc;
                if (self->tone_phase[ch] >= 1.0)
                    self->tone_phase[ch] -= floor(self->tone_phase[ch]);
            }
        }
        mix += sample * v;
    }

    v = sn_vol_table[self->noise_vol & 0x0F];
    if (v > 0.0f)
        mix += (self->noise_out ? 1.0f : -1.0f) * v;

    mix *= self->master_gain;
    if (mix > 1.0f)
        mix = 1.0f;
    else if (mix < -1.0f)
        mix = -1.0f;
    return mix;
}

static float
sn_mix_one(SN76496Object *self)
{
    int cycles = (int)(self->clocks_per_sample + 0.5);
    if (cycles < 1)
        cycles = 1;
    sn_clock_chip(self, cycles);
    return sn_mix_sample(self);
}

static PyObject *
sn_render_into(SN76496Object *self, PyObject *args)
{
    Py_buffer view;
    Py_ssize_t n, i;
    float *out;

    if (parse_float_buf(args, &view, &out, &n) < 0)
        return NULL;
    for (i = 0; i < n; i++)
        out[i] = sn_mix_one(self);
    PyBuffer_Release(&view);
    Py_RETURN_NONE;
}

static PyObject *
sn_tone_frequency(SN76496Object *self, PyObject *args)
{
    int ch;
    uint16_t p;
    if (!PyArg_ParseTuple(args, "i", &ch))
        return NULL;
    if (ch < 0 || ch > 2) {
        PyErr_SetString(PyExc_ValueError, "channel must be 0..2");
        return NULL;
    }
    p = self->tone_period[ch];
    if (p == 0)
        return PyFloat_FromDouble(0.0);
    return PyFloat_FromDouble(self->clock_hz / (32.0 * (double)p));
}

static PyObject *
sn_get_sample_rate(SN76496Object *self, void *Py_UNUSED(closure))
{
    return PyFloat_FromDouble(self->sample_rate);
}

static PyObject *
sn_get_clock(SN76496Object *self, void *Py_UNUSED(closure))
{
    return PyFloat_FromDouble(self->clock_hz);
}

static PyObject *
sn_get_variant(SN76496Object *self, void *Py_UNUSED(closure))
{
    return PyLong_FromLong(self->variant);
}

static PyGetSetDef sn_getset[] = {
    {"sample_rate", (getter)sn_get_sample_rate, NULL, NULL, NULL},
    {"clock_hz", (getter)sn_get_clock, NULL, NULL, NULL},
    {"variant", (getter)sn_get_variant, NULL, NULL, NULL},
    {NULL}
};

static PyMethodDef sn_methods[] = {
    {"reset", (PyCFunction)sn_reset, METH_NOARGS, NULL},
    {"write", (PyCFunction)sn_write, METH_VARARGS,
     "write(value) or write(addr, value) — TI PSG data byte."},
    {"set_tone", (PyCFunction)(void (*)(void))sn_set_tone,
     METH_VARARGS | METH_KEYWORDS, NULL},
    {"set_noise", (PyCFunction)(void (*)(void))sn_set_noise,
     METH_VARARGS | METH_KEYWORDS, NULL},
    {"set_tone_waveform", (PyCFunction)sn_set_tone_waveform, METH_VARARGS, NULL},
    {"tone_frequency", (PyCFunction)sn_tone_frequency, METH_VARARGS, NULL},
    {"render_into", (PyCFunction)sn_render_into, METH_VARARGS,
     "Render mono float32 samples into a writable buffer."},
    {NULL}
};

static PyTypeObject SN76496Type = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "rwt_rsound._chips.SN76496Core",
    .tp_basicsize = sizeof(SN76496Object),
    .tp_flags = Py_TPFLAGS_DEFAULT,
    .tp_doc = "SN76489-family PSG (Tandy SN76496 / Sega SMS PSG variants).",
    .tp_methods = sn_methods,
    .tp_getset = sn_getset,
    .tp_init = (initproc)sn_init,
    .tp_new = PyType_GenericNew,
};

/* --- module ------------------------------------------------------------- */

static struct PyModuleDef moduledef = {
    PyModuleDef_HEAD_INIT,
    .m_name = "_chips",
    .m_doc = "C cores for rwt_rsound chips (synthesis only).",
    .m_size = -1,
};

PyMODINIT_FUNC
PyInit__chips(void)
{
    PyObject *m;

    if (PyType_Ready(&PCSpeakerType) < 0)
        return NULL;
    if (PyType_Ready(&SN76496Type) < 0)
        return NULL;

    m = PyModule_Create(&moduledef);
    if (m == NULL)
        return NULL;

    Py_INCREF(&PCSpeakerType);
    if (PyModule_AddObject(m, "PCSpeakerCore", (PyObject *)&PCSpeakerType) < 0) {
        Py_DECREF(&PCSpeakerType);
        Py_DECREF(m);
        return NULL;
    }
    Py_INCREF(&SN76496Type);
    if (PyModule_AddObject(m, "SN76496Core", (PyObject *)&SN76496Type) < 0) {
        Py_DECREF(&SN76496Type);
        Py_DECREF(m);
        return NULL;
    }
    if (rwt_nes_apu_add_to_module(m) < 0) {
        Py_DECREF(m);
        return NULL;
    }

    PyModule_AddIntConstant(m, "WAVE_SQUARE", RWT_WAVE_SQUARE);
    PyModule_AddIntConstant(m, "WAVE_TRIANGLE", RWT_WAVE_TRIANGLE);
    PyModule_AddIntConstant(m, "WAVE_SAWTOOTH", RWT_WAVE_SAWTOOTH);
    PyModule_AddIntConstant(m, "WAVE_SINE", RWT_WAVE_SINE);
    PyModule_AddIntConstant(m, "VARIANT_TANDY", SN_VARIANT_TANDY);
    PyModule_AddIntConstant(m, "VARIANT_SEGA", SN_VARIANT_SEGA);
    PyModule_AddIntConstant(m, "PIT_CLOCK_HZ", 1193182);

    return m;
}
