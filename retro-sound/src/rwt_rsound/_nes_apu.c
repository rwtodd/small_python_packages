/*
 * NES APU core — cycle-stepped for CPU/PPU interleaving in full emulators.
 *
 * Timing model (NTSC/PAL CPU clocks):
 *   - Call clock(cpu_cycles) from the CPU side each instruction / timeslice
 *   - Channel timers advance every APU cycle (2 CPU cycles)
 *   - Frame sequencer clocks envelopes / length / sweep on fixed CPU-cycle steps
 *   - PCM samples are produced into a ring buffer as cycles accumulate
 *
 * Registers: $4000–$4013, $4015, $4017 (CPU address bus low 16 bits accepted).
 * DMC can fetch sample bytes via an optional Python callable(addr) -> int.
 */

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <math.h>
#include <stdint.h>
#include <string.h>

/* Forward: registered from this file into rwt_rsound._chips */
int rwt_nes_apu_add_to_module(PyObject *m);

enum {
    NES_REGION_NTSC = 0,
    NES_REGION_PAL = 1,
};

#define NES_RING_SIZE 8192

/* CPU clocks (approx) */
#define NES_NTSC_CPU_HZ 1789773.0
#define NES_PAL_CPU_HZ  1662607.0

static const uint8_t LENGTH_TABLE[32] = {
    10, 254, 20, 2, 40, 4, 80, 6, 160, 8, 60, 10, 14, 12, 26, 14,
    12, 16, 24, 18, 48, 20, 96, 22, 192, 24, 72, 26, 16, 28, 32, 30
};

static const uint8_t DUTY_TABLE[4][8] = {
    {0, 1, 0, 0, 0, 0, 0, 0},
    {0, 1, 1, 0, 0, 0, 0, 0},
    {0, 1, 1, 1, 1, 0, 0, 0},
    {1, 0, 0, 1, 1, 1, 1, 1},
};

static const uint8_t TRI_SEQUENCE[32] = {
    15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0,
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15
};

/* NTSC noise timer periods (APU cycles) */
static const uint16_t NOISE_PERIOD_NTSC[16] = {
    4, 8, 16, 32, 64, 96, 128, 160, 202, 254, 380, 508, 762, 1016, 2034, 4068
};

static const uint16_t NOISE_PERIOD_PAL[16] = {
    4, 8, 14, 30, 60, 88, 118, 148, 188, 236, 354, 472, 708, 944, 1890, 3778
};

/* DMC rate index → CPU cycles per bit */
static const uint16_t DMC_RATE_NTSC[16] = {
    428, 380, 340, 320, 286, 254, 226, 214, 190, 160, 142, 128, 106, 84, 72, 54
};

static const uint16_t DMC_RATE_PAL[16] = {
    398, 354, 316, 298, 276, 236, 210, 198, 176, 148, 132, 118, 98, 78, 66, 50
};

/* Frame sequencer step times in CPU cycles (from reset / $4017 write).
 * Values match common NESDev-derived integer schedules (slightly idealized). */
static const int FRAME_MODE0_CPU[4] = {7457, 14913, 22371, 29829};
static const int FRAME_MODE1_CPU[5] = {7457, 14913, 22371, 29829, 37281};

/* --- pulse channel ------------------------------------------------------ */

typedef struct {
    /* regs */
    uint8_t duty;
    uint8_t envelope_loop; /* also length halt */
    uint8_t constant_volume;
    uint8_t volume; /* envelope period or const volume */
    uint8_t sweep_enabled;
    uint8_t sweep_period;
    uint8_t sweep_negate;
    uint8_t sweep_shift;
    uint16_t timer_period; /* 11-bit */
    uint8_t length_counter;

    /* envelope unit */
    uint8_t envelope_start;
    uint8_t envelope_divider;
    uint8_t envelope_decay; /* 0..15 */

    /* sweep unit */
    uint8_t sweep_reload;
    uint8_t sweep_divider;

    /* timer / sequencer */
    uint16_t timer;
    uint8_t duty_step; /* 0..7 */
    uint8_t enabled;
    int channel_index; /* 0 or 1 — sweep negate ones-complement vs twos */
} PulseChan;

/* --- triangle ----------------------------------------------------------- */

typedef struct {
    uint8_t control; /* length halt / linear control flag */
    uint8_t linear_reload_value;
    uint8_t length_counter;
    uint16_t timer_period;
    uint16_t timer;
    uint8_t linear_counter;
    uint8_t linear_reload_flag;
    uint8_t seq_step;
    uint8_t enabled;
} TriangleChan;

/* --- noise -------------------------------------------------------------- */

typedef struct {
    uint8_t envelope_loop;
    uint8_t constant_volume;
    uint8_t volume;
    uint8_t mode; /* 1 = short loop (bit 6 feedback) */
    uint8_t period_index;
    uint8_t length_counter;

    uint8_t envelope_start;
    uint8_t envelope_divider;
    uint8_t envelope_decay;

    uint16_t timer;
    uint16_t shift; /* 15-bit LFSR */
    uint8_t enabled;
} NoiseChan;

/* --- DMC ---------------------------------------------------------------- */

typedef struct {
    uint8_t irq_enabled;
    uint8_t loop;
    uint8_t rate_index;
    uint16_t sample_address; /* $C000 + (addr * 64) */
    uint16_t sample_length;  /* (len * 16) + 1 */

    uint16_t current_address;
    uint16_t bytes_remaining;
    uint8_t sample_buffer;
    uint8_t sample_buffer_full;
    uint8_t shift_register;
    uint8_t bits_remaining;
    uint8_t silence;
    uint8_t output_level; /* 0..127 */
    uint16_t timer;
    uint8_t irq_flag;
    uint8_t enabled;
} DmcChan;

/* --- APU object --------------------------------------------------------- */

typedef struct {
    PyObject_HEAD
    int region; /* NTSC / PAL */
    double cpu_clock_hz;
    double sample_rate;
    float master_gain;

    PulseChan pulse[2];
    TriangleChan triangle;
    NoiseChan noise;
    DmcChan dmc;

    /* frame counter */
    uint8_t frame_mode;       /* 0=4-step, 1=5-step */
    uint8_t frame_irq_inhibit;
    uint8_t frame_irq_flag;
    int frame_cycle;          /* CPU cycles into current frame sequence */
    int frame_step;           /* next step index */
    int odd_cycle;            /* for APU cycle = every 2 CPU */

    /* optional DMC memory reader: callable(addr:int) -> int */
    PyObject *dmc_reader;

    /* sample ring */
    float ring[NES_RING_SIZE];
    int ring_r;
    int ring_w;
    int ring_count;
    double sample_cycle_accum;
    double cycles_per_sample;
} NesApuObject;

static const uint16_t *
noise_periods(const NesApuObject *self)
{
    return self->region == NES_REGION_PAL ? NOISE_PERIOD_PAL : NOISE_PERIOD_NTSC;
}

static const uint16_t *
dmc_rates(const NesApuObject *self)
{
    return self->region == NES_REGION_PAL ? DMC_RATE_PAL : DMC_RATE_NTSC;
}

/* --- envelope ----------------------------------------------------------- */

static void
envelope_clock(uint8_t *start, uint8_t *divider, uint8_t *decay,
               uint8_t loop, uint8_t period_or_vol)
{
    if (*start) {
        *start = 0;
        *decay = 15;
        *divider = period_or_vol;
        return;
    }
    if (*divider > 0) {
        (*divider)--;
        return;
    }
    *divider = period_or_vol;
    if (*decay > 0)
        (*decay)--;
    else if (loop)
        *decay = 15;
}

static uint8_t
envelope_output(uint8_t constant_volume, uint8_t volume, uint8_t decay)
{
    return constant_volume ? volume : decay;
}

/* --- pulse helpers ------------------------------------------------------ */

static int
pulse_target_period(const PulseChan *p)
{
    int change = p->timer_period >> p->sweep_shift;
    if (p->sweep_negate) {
        /* pulse 1: ones' complement; pulse 2: two's complement */
        if (p->channel_index == 0)
            return (int)p->timer_period - change - 1;
        return (int)p->timer_period - change;
    }
    return (int)p->timer_period + change;
}

static int
pulse_muted(const PulseChan *p)
{
    int target;
    if (p->timer_period < 8)
        return 1;
    target = pulse_target_period(p);
    if (target > 0x7FF)
        return 1;
    return 0;
}

static void
pulse_clock_timer(PulseChan *p)
{
    if (p->timer == 0) {
        p->timer = p->timer_period;
        p->duty_step = (uint8_t)((p->duty_step + 1) & 7);
    } else {
        p->timer--;
    }
}

static void
pulse_clock_sweep(PulseChan *p)
{
    int target;
    int timed_out = (p->sweep_divider == 0);
    if (timed_out && p->sweep_enabled && p->sweep_shift > 0 && !pulse_muted(p)) {
        target = pulse_target_period(p);
        if (target >= 0 && target <= 0x7FF)
            p->timer_period = (uint16_t)target;
    }
    if (timed_out || p->sweep_reload) {
        p->sweep_divider = p->sweep_period;
        p->sweep_reload = 0;
    } else if (p->sweep_divider > 0) {
        p->sweep_divider--;
    }
}

static uint8_t
pulse_output(const PulseChan *p)
{
    uint8_t vol;
    if (!p->enabled || p->length_counter == 0)
        return 0;
    if (pulse_muted(p))
        return 0;
    if (!DUTY_TABLE[p->duty & 3][p->duty_step & 7])
        return 0;
    vol = envelope_output(p->constant_volume, p->volume, p->envelope_decay);
    return vol;
}

/* --- triangle ----------------------------------------------------------- */

static void
triangle_clock_timer(TriangleChan *t)
{
    if (t->timer == 0) {
        t->timer = t->timer_period;
        if (t->length_counter > 0 && t->linear_counter > 0)
            t->seq_step = (uint8_t)((t->seq_step + 1) & 31);
    } else {
        t->timer--;
    }
}

static void
triangle_clock_linear(TriangleChan *t)
{
    if (t->linear_reload_flag)
        t->linear_counter = t->linear_reload_value;
    else if (t->linear_counter > 0)
        t->linear_counter--;
    if (!t->control)
        t->linear_reload_flag = 0;
}

static uint8_t
triangle_output(const TriangleChan *t)
{
    if (!t->enabled || t->length_counter == 0 || t->linear_counter == 0)
        return 0;
    /* ultrasonic mute when period < 2 is sometimes applied; skip for music */
    return TRI_SEQUENCE[t->seq_step & 31];
}

/* --- noise -------------------------------------------------------------- */

static void
noise_clock_timer_full(NoiseChan *n, const uint16_t *periods)
{
    if (n->timer == 0) {
        uint16_t bit0 = n->shift & 1;
        uint16_t other = n->mode ? ((n->shift >> 6) & 1) : ((n->shift >> 1) & 1);
        uint16_t feedback = bit0 ^ other;
        n->shift = (uint16_t)((n->shift >> 1) | (feedback << 14));
        n->timer = periods[n->period_index & 15];
    } else {
        n->timer--;
    }
}

static uint8_t
noise_output(const NoiseChan *n)
{
    uint8_t vol;
    if (!n->enabled || n->length_counter == 0)
        return 0;
    if (n->shift & 1)
        return 0;
    vol = envelope_output(n->constant_volume, n->volume, n->envelope_decay);
    return vol;
}

/* --- DMC ---------------------------------------------------------------- */

static int
dmc_read_byte(NesApuObject *self, uint16_t addr, uint8_t *out)
{
    PyObject *res;
    long v;
    if (self->dmc_reader == NULL || self->dmc_reader == Py_None) {
        *out = 0;
        return 0;
    }
    res = PyObject_CallFunction(self->dmc_reader, "I", (unsigned int)addr);
    if (res == NULL)
        return -1;
    v = PyLong_AsLong(res);
    Py_DECREF(res);
    if (v == -1 && PyErr_Occurred())
        return -1;
    *out = (uint8_t)(v & 0xFF);
    return 0;
}

static void
dmc_start_sample(DmcChan *d)
{
    d->current_address = d->sample_address;
    d->bytes_remaining = d->sample_length;
}

static void
dmc_fill_sample_buffer(NesApuObject *self)
{
    DmcChan *d = &self->dmc;
    uint8_t byte;
    if (d->sample_buffer_full || d->bytes_remaining == 0)
        return;
    if (dmc_read_byte(self, d->current_address, &byte) < 0) {
        /* leave error set; caller checks */
        return;
    }
    d->sample_buffer = byte;
    d->sample_buffer_full = 1;
    d->current_address = (uint16_t)(0x8000 | ((d->current_address + 1) & 0x7FFF));
    d->bytes_remaining--;
    if (d->bytes_remaining == 0) {
        if (d->loop)
            dmc_start_sample(d);
        else if (d->irq_enabled)
            d->irq_flag = 1;
    }
}

static void
dmc_clock_timer(NesApuObject *self)
{
    DmcChan *d = &self->dmc;
    if (d->timer == 0) {
        d->timer = dmc_rates(self)[d->rate_index & 15];
        if (!d->silence) {
            if (d->shift_register & 1) {
                if (d->output_level <= 125)
                    d->output_level = (uint8_t)(d->output_level + 2);
            } else {
                if (d->output_level >= 2)
                    d->output_level = (uint8_t)(d->output_level - 2);
            }
            d->shift_register >>= 1;
        }
        d->bits_remaining--;
        if (d->bits_remaining == 0) {
            d->bits_remaining = 8;
            if (d->sample_buffer_full) {
                d->silence = 0;
                d->shift_register = d->sample_buffer;
                d->sample_buffer_full = 0;
            } else {
                d->silence = 1;
            }
        }
        dmc_fill_sample_buffer(self);
    } else {
        d->timer--;
    }
}

/* --- length counters ---------------------------------------------------- */

static void
clock_length_counters(NesApuObject *self)
{
    int i;
    for (i = 0; i < 2; i++) {
        if (self->pulse[i].length_counter > 0 && !self->pulse[i].envelope_loop)
            self->pulse[i].length_counter--;
    }
    if (self->triangle.length_counter > 0 && !self->triangle.control)
        self->triangle.length_counter--;
    if (self->noise.length_counter > 0 && !self->noise.envelope_loop)
        self->noise.length_counter--;
}

static void
clock_envelopes_and_linear(NesApuObject *self)
{
    int i;
    for (i = 0; i < 2; i++) {
        envelope_clock(&self->pulse[i].envelope_start,
                       &self->pulse[i].envelope_divider,
                       &self->pulse[i].envelope_decay,
                       self->pulse[i].envelope_loop,
                       self->pulse[i].volume);
    }
    envelope_clock(&self->noise.envelope_start,
                   &self->noise.envelope_divider,
                   &self->noise.envelope_decay,
                   self->noise.envelope_loop,
                   self->noise.volume);
    triangle_clock_linear(&self->triangle);
}

static void
clock_sweeps(NesApuObject *self)
{
    pulse_clock_sweep(&self->pulse[0]);
    pulse_clock_sweep(&self->pulse[1]);
}

static void
frame_quarter(NesApuObject *self)
{
    clock_envelopes_and_linear(self);
}

static void
frame_half(NesApuObject *self)
{
    clock_length_counters(self);
    clock_sweeps(self);
}

/* --- mixer (NESDev nonlinear → bipolar float) --------------------------- */

static float
mix_final(NesApuObject *self)
{
    int p1 = pulse_output(&self->pulse[0]);
    int p2 = pulse_output(&self->pulse[1]);
    int t = triangle_output(&self->triangle);
    int n = noise_output(&self->noise);
    int d = self->dmc.enabled ? self->dmc.output_level : 0;
    float pulse_out = 0.0f;
    float tnd_out = 0.0f;
    float mixed;

    if (p1 + p2 > 0)
        pulse_out = 95.88f / ((8128.0f / (float)(p1 + p2)) + 100.0f);
    if (t || n || d)
        tnd_out = 159.79f / (100.0f + 1.0f / (((float)t / 8227.0f) +
                                              ((float)n / 12241.0f) +
                                              ((float)d / 22638.0f)));
    mixed = pulse_out + tnd_out; /* ~0..1 hardware-style level */
    if (mixed <= 0.0f)
        return 0.0f;
    /* Unipolar NES mix → bipolar PCM around 0 (silent = 0). */
    return (mixed - 0.5f) * 2.0f * self->master_gain;
}

static void
ring_push(NesApuObject *self, float s)
{
    if (self->ring_count >= NES_RING_SIZE) {
        /* drop oldest */
        self->ring_r = (self->ring_r + 1) % NES_RING_SIZE;
        self->ring_count--;
    }
    self->ring[self->ring_w] = s;
    self->ring_w = (self->ring_w + 1) % NES_RING_SIZE;
    self->ring_count++;
}

static int
ring_pop(NesApuObject *self, float *s)
{
    if (self->ring_count <= 0)
        return 0;
    *s = self->ring[self->ring_r];
    self->ring_r = (self->ring_r + 1) % NES_RING_SIZE;
    self->ring_count--;
    return 1;
}

/* --- frame sequencer ---------------------------------------------------- */

static void
frame_sequencer_step(NesApuObject *self)
{
    if (self->frame_mode == 0) {
        /* 4-step */
        switch (self->frame_step) {
        case 0:
            frame_quarter(self);
            break;
        case 1:
            frame_quarter(self);
            frame_half(self);
            break;
        case 2:
            frame_quarter(self);
            break;
        case 3:
            frame_quarter(self);
            frame_half(self);
            if (!self->frame_irq_inhibit)
                self->frame_irq_flag = 1;
            break;
        }
        self->frame_step++;
        if (self->frame_step >= 4) {
            self->frame_step = 0;
            self->frame_cycle = 0;
        }
    } else {
        /* 5-step */
        switch (self->frame_step) {
        case 0:
            frame_quarter(self);
            break;
        case 1:
            frame_quarter(self);
            frame_half(self);
            break;
        case 2:
            frame_quarter(self);
            break;
        case 3:
            /* idle */
            break;
        case 4:
            frame_quarter(self);
            frame_half(self);
            break;
        }
        self->frame_step++;
        if (self->frame_step >= 5) {
            self->frame_step = 0;
            self->frame_cycle = 0;
        }
    }
}

static void
frame_counter_cpu_tick(NesApuObject *self)
{
    const int *table;
    int nsteps;
    int target;

    self->frame_cycle++;
    if (self->frame_mode == 0) {
        table = FRAME_MODE0_CPU;
        nsteps = 4;
    } else {
        table = FRAME_MODE1_CPU;
        nsteps = 5;
    }
    if (self->frame_step < nsteps) {
        target = table[self->frame_step];
        /* targets are absolute from sequence start; frame_cycle counts from 0
         * after each full loop reset. Use cumulative: after reset frame_cycle
         * goes 1..target[0], then we need absolute positions.
         * We store frame_cycle from start of sequence (not reset each step). */
        if (self->frame_cycle >= target)
            frame_sequencer_step(self);
    }
}

/* Wait - there's a bug: after step 0, frame_step becomes 1 but frame_cycle
 * continues, and we compare to table[1] which is absolute from start. Good.
 * After step 3/4 we reset frame_cycle to 0. Good.
 * But when we fire step 0 at 7457, we don't reset cycle - good.
 */

/* --- clock one CPU cycle ------------------------------------------------ */

static int
apu_clock_one(NesApuObject *self)
{
    /* APU cycle on every other CPU cycle */
    self->odd_cycle ^= 1;
    if (!self->odd_cycle) {
        pulse_clock_timer(&self->pulse[0]);
        pulse_clock_timer(&self->pulse[1]);
        triangle_clock_timer(&self->triangle);
        noise_clock_timer_full(&self->noise, noise_periods(self));
        dmc_clock_timer(self);
        if (PyErr_Occurred())
            return -1;
    }

    frame_counter_cpu_tick(self);

    /* sample generation */
    self->sample_cycle_accum += 1.0;
    while (self->sample_cycle_accum >= self->cycles_per_sample) {
        self->sample_cycle_accum -= self->cycles_per_sample;
        ring_push(self, mix_final(self));
    }
    return 0;
}

static int
apu_clock(NesApuObject *self, long cycles)
{
    long i;
    if (cycles < 0) {
        PyErr_SetString(PyExc_ValueError, "cpu_cycles must be >= 0");
        return -1;
    }
    for (i = 0; i < cycles; i++) {
        if (apu_clock_one(self) < 0)
            return -1;
    }
    return 0;
}

/* --- register write/read ------------------------------------------------ */

static void
write_pulse_reg(PulseChan *p, int reg, int value)
{
    switch (reg & 3) {
    case 0:
        p->duty = (uint8_t)((value >> 6) & 3);
        p->envelope_loop = (value >> 5) & 1;
        p->constant_volume = (value >> 4) & 1;
        p->volume = (uint8_t)(value & 0x0F);
        break;
    case 1:
        p->sweep_enabled = (value >> 7) & 1;
        p->sweep_period = (uint8_t)((value >> 4) & 7);
        p->sweep_negate = (value >> 3) & 1;
        p->sweep_shift = (uint8_t)(value & 7);
        p->sweep_reload = 1;
        break;
    case 2:
        p->timer_period = (uint16_t)((p->timer_period & 0x700) | (value & 0xFF));
        break;
    case 3:
        p->timer_period =
            (uint16_t)((p->timer_period & 0x00FF) | ((value & 7) << 8));
        p->length_counter = p->enabled ? LENGTH_TABLE[(value >> 3) & 0x1F] : 0;
        p->duty_step = 0;
        p->envelope_start = 1;
        break;
    }
}

static void
apu_write(NesApuObject *self, int addr, int value)
{
    int a = addr & 0xFFFF;
    value &= 0xFF;

    if (a >= 0x4000 && a <= 0x4003) {
        write_pulse_reg(&self->pulse[0], a - 0x4000, value);
        return;
    }
    if (a >= 0x4004 && a <= 0x4007) {
        write_pulse_reg(&self->pulse[1], a - 0x4004, value);
        return;
    }
    if (a == 0x4008) {
        self->triangle.control = (value >> 7) & 1;
        self->triangle.linear_reload_value = (uint8_t)(value & 0x7F);
        return;
    }
    if (a == 0x400A) {
        self->triangle.timer_period =
            (uint16_t)((self->triangle.timer_period & 0x700) | (value & 0xFF));
        return;
    }
    if (a == 0x400B) {
        self->triangle.timer_period =
            (uint16_t)((self->triangle.timer_period & 0x00FF) | ((value & 7) << 8));
        self->triangle.length_counter =
            self->triangle.enabled ? LENGTH_TABLE[(value >> 3) & 0x1F] : 0;
        self->triangle.linear_reload_flag = 1;
        return;
    }
    if (a == 0x400C) {
        self->noise.envelope_loop = (value >> 5) & 1;
        self->noise.constant_volume = (value >> 4) & 1;
        self->noise.volume = (uint8_t)(value & 0x0F);
        return;
    }
    if (a == 0x400E) {
        self->noise.mode = (value >> 7) & 1;
        self->noise.period_index = (uint8_t)(value & 0x0F);
        return;
    }
    if (a == 0x400F) {
        self->noise.length_counter =
            self->noise.enabled ? LENGTH_TABLE[(value >> 3) & 0x1F] : 0;
        self->noise.envelope_start = 1;
        return;
    }
    if (a == 0x4010) {
        self->dmc.irq_enabled = (value >> 7) & 1;
        self->dmc.loop = (value >> 6) & 1;
        self->dmc.rate_index = (uint8_t)(value & 0x0F);
        if (!self->dmc.irq_enabled)
            self->dmc.irq_flag = 0;
        return;
    }
    if (a == 0x4011) {
        self->dmc.output_level = (uint8_t)(value & 0x7F);
        return;
    }
    if (a == 0x4012) {
        self->dmc.sample_address = (uint16_t)(0xC000 + (value * 64));
        return;
    }
    if (a == 0x4013) {
        self->dmc.sample_length = (uint16_t)(value * 16 + 1);
        return;
    }
    if (a == 0x4015) {
        self->pulse[0].enabled = value & 1;
        self->pulse[1].enabled = (value >> 1) & 1;
        self->triangle.enabled = (value >> 2) & 1;
        self->noise.enabled = (value >> 3) & 1;
        self->dmc.enabled = (value >> 4) & 1;
        if (!self->pulse[0].enabled)
            self->pulse[0].length_counter = 0;
        if (!self->pulse[1].enabled)
            self->pulse[1].length_counter = 0;
        if (!self->triangle.enabled)
            self->triangle.length_counter = 0;
        if (!self->noise.enabled)
            self->noise.length_counter = 0;
        if (!self->dmc.enabled) {
            self->dmc.bytes_remaining = 0;
        } else if (self->dmc.bytes_remaining == 0) {
            dmc_start_sample(&self->dmc);
        }
        self->dmc.irq_flag = 0;
        return;
    }
    if (a == 0x4017) {
        self->frame_mode = (value >> 7) & 1;
        self->frame_irq_inhibit = (value >> 6) & 1;
        if (self->frame_irq_inhibit)
            self->frame_irq_flag = 0;
        self->frame_cycle = 0;
        self->frame_step = 0;
        /* Mode 1: clock quarter+half immediately (approx; real HW delays 3-4 cycles) */
        if (self->frame_mode) {
            frame_quarter(self);
            frame_half(self);
        }
        return;
    }
}

static int
apu_read(NesApuObject *self, int addr)
{
    int a = addr & 0xFFFF;
    int result;
    if (a != 0x4015)
        return 0;
    result = 0;
    if (self->pulse[0].length_counter > 0)
        result |= 0x01;
    if (self->pulse[1].length_counter > 0)
        result |= 0x02;
    if (self->triangle.length_counter > 0)
        result |= 0x04;
    if (self->noise.length_counter > 0)
        result |= 0x08;
    if (self->dmc.bytes_remaining > 0)
        result |= 0x10;
    if (self->frame_irq_flag)
        result |= 0x40;
    if (self->dmc.irq_flag)
        result |= 0x80;
    /* reading $4015 clears frame IRQ */
    self->frame_irq_flag = 0;
    return result;
}

/* --- reset / init ------------------------------------------------------- */

static void
apu_reset_state(NesApuObject *self)
{
    int i;
    memset(&self->pulse, 0, sizeof(self->pulse));
    memset(&self->triangle, 0, sizeof(self->triangle));
    memset(&self->noise, 0, sizeof(self->noise));
    memset(&self->dmc, 0, sizeof(self->dmc));
    self->pulse[0].channel_index = 0;
    self->pulse[1].channel_index = 1;
    self->noise.shift = 1;
    self->dmc.silence = 1;
    self->dmc.bits_remaining = 8;
    self->frame_mode = 0;
    self->frame_irq_inhibit = 0;
    self->frame_irq_flag = 0;
    self->frame_cycle = 0;
    self->frame_step = 0;
    self->odd_cycle = 0;
    self->ring_r = self->ring_w = self->ring_count = 0;
    self->sample_cycle_accum = 0.0;
    for (i = 0; i < 2; i++)
        self->pulse[i].timer_period = 0;
    self->triangle.timer_period = 0;
    /* silence channels until $4015 enables */
}

static int
nes_init(NesApuObject *self, PyObject *args, PyObject *kw)
{
    static char *kwlist[] = {"sample_rate", "region", "cpu_clock_hz",
                             "master_gain", NULL};
    double sr = 44100.0;
    int region = NES_REGION_NTSC;
    double cpu = 0.0;
    double gain = 0.5;

    if (!PyArg_ParseTupleAndKeywords(args, kw, "|didd", kwlist,
                                     &sr, &region, &cpu, &gain))
        return -1;
    if (sr <= 0.0) {
        PyErr_SetString(PyExc_ValueError, "sample_rate must be positive");
        return -1;
    }
    if (region != NES_REGION_NTSC && region != NES_REGION_PAL) {
        PyErr_SetString(PyExc_ValueError, "region must be 0 (NTSC) or 1 (PAL)");
        return -1;
    }
    if (gain < 0.0 || gain > 1.0) {
        PyErr_SetString(PyExc_ValueError, "master_gain must be 0..1");
        return -1;
    }
    if (cpu <= 0.0)
        cpu = (region == NES_REGION_PAL) ? NES_PAL_CPU_HZ : NES_NTSC_CPU_HZ;

    self->region = region;
    self->sample_rate = sr;
    self->cpu_clock_hz = cpu;
    self->master_gain = (float)gain;
    self->cycles_per_sample = cpu / sr;
    self->dmc_reader = NULL;
    apu_reset_state(self);
    return 0;
}

static void
nes_dealloc(NesApuObject *self)
{
    Py_XDECREF(self->dmc_reader);
    Py_TYPE(self)->tp_free((PyObject *)self);
}

static PyObject *
nes_reset(NesApuObject *self, PyObject *Py_UNUSED(ignored))
{
    apu_reset_state(self);
    Py_RETURN_NONE;
}

static PyObject *
nes_clock(NesApuObject *self, PyObject *args)
{
    long cycles;
    if (!PyArg_ParseTuple(args, "l", &cycles))
        return NULL;
    if (apu_clock(self, cycles) < 0)
        return NULL;
    return PyLong_FromLong(self->ring_count);
}

static PyObject *
nes_write(NesApuObject *self, PyObject *args)
{
    int addr, value;
    if (!PyArg_ParseTuple(args, "ii", &addr, &value))
        return NULL;
    apu_write(self, addr, value);
    Py_RETURN_NONE;
}

static PyObject *
nes_read(NesApuObject *self, PyObject *args)
{
    int addr;
    if (!PyArg_ParseTuple(args, "i", &addr))
        return NULL;
    return PyLong_FromLong(apu_read(self, addr));
}

static PyObject *
nes_samples_available(NesApuObject *self, PyObject *Py_UNUSED(ignored))
{
    return PyLong_FromLong(self->ring_count);
}

static PyObject *
nes_irq_pending(NesApuObject *self, PyObject *Py_UNUSED(ignored))
{
    int pending = (self->frame_irq_flag || self->dmc.irq_flag) ? 1 : 0;
    return PyBool_FromLong(pending);
}

static PyObject *
nes_set_dmc_reader(NesApuObject *self, PyObject *args)
{
    PyObject *cb;
    if (!PyArg_ParseTuple(args, "O", &cb))
        return NULL;
    if (cb != Py_None && !PyCallable_Check(cb)) {
        PyErr_SetString(PyExc_TypeError, "dmc_reader must be callable or None");
        return NULL;
    }
    if (cb == Py_None) {
        Py_XDECREF(self->dmc_reader);
        self->dmc_reader = NULL;
    } else {
        Py_INCREF(cb);
        Py_XDECREF(self->dmc_reader);
        self->dmc_reader = cb;
    }
    Py_RETURN_NONE;
}

static PyObject *
nes_drain_into(NesApuObject *self, PyObject *args)
{
    Py_buffer view;
    Py_ssize_t n, i;
    float *out;
    float s;

    if (!PyArg_ParseTuple(args, "w*", &view))
        return NULL;
    if (view.len % (Py_ssize_t)sizeof(float) != 0) {
        PyBuffer_Release(&view);
        PyErr_SetString(PyExc_ValueError, "buffer length must be multiple of 4");
        return NULL;
    }
    if (view.readonly) {
        PyBuffer_Release(&view);
        PyErr_SetString(PyExc_BufferError, "buffer must be writable");
        return NULL;
    }
    out = (float *)view.buf;
    n = view.len / (Py_ssize_t)sizeof(float);
    for (i = 0; i < n; i++) {
        if (!ring_pop(self, &s))
            s = 0.0f;
        out[i] = s;
    }
    PyBuffer_Release(&view);
    Py_RETURN_NONE;
}

static PyObject *
nes_render_into(NesApuObject *self, PyObject *args)
{
    Py_buffer view;
    Py_ssize_t n, i;
    float *out;
    float s;
    long guard;

    if (!PyArg_ParseTuple(args, "w*", &view))
        return NULL;
    if (view.len % (Py_ssize_t)sizeof(float) != 0) {
        PyBuffer_Release(&view);
        PyErr_SetString(PyExc_ValueError, "buffer length must be multiple of 4");
        return NULL;
    }
    if (view.readonly) {
        PyBuffer_Release(&view);
        PyErr_SetString(PyExc_BufferError, "buffer must be writable");
        return NULL;
    }
    out = (float *)view.buf;
    n = view.len / (Py_ssize_t)sizeof(float);

    /* Offline path: clock until each sample is produced (preserves ring timing). */
    for (i = 0; i < n; i++) {
        guard = 0;
        while (self->ring_count <= 0) {
            if (apu_clock_one(self) < 0) {
                PyBuffer_Release(&view);
                return NULL;
            }
            if (++guard > 1000000) {
                PyBuffer_Release(&view);
                PyErr_SetString(PyExc_RuntimeError,
                                "NES APU render stalled (no samples)");
                return NULL;
            }
        }
        ring_pop(self, &s);
        out[i] = s;
    }
    PyBuffer_Release(&view);
    Py_RETURN_NONE;
}

static PyObject *
nes_get_sample_rate(NesApuObject *self, void *Py_UNUSED(c))
{
    return PyFloat_FromDouble(self->sample_rate);
}

static PyObject *
nes_get_cpu_clock(NesApuObject *self, void *Py_UNUSED(c))
{
    return PyFloat_FromDouble(self->cpu_clock_hz);
}

static PyObject *
nes_get_region(NesApuObject *self, void *Py_UNUSED(c))
{
    return PyLong_FromLong(self->region);
}

static PyGetSetDef nes_getset[] = {
    {"sample_rate", (getter)nes_get_sample_rate, NULL, NULL, NULL},
    {"cpu_clock_hz", (getter)nes_get_cpu_clock, NULL, NULL, NULL},
    {"region", (getter)nes_get_region, NULL, NULL, NULL},
    {NULL}
};

static PyMethodDef nes_methods[] = {
    {"reset", (PyCFunction)nes_reset, METH_NOARGS, "Reset APU state."},
    {"clock", (PyCFunction)nes_clock, METH_VARARGS,
     "clock(cpu_cycles) -> samples_available\n"
     "Advance the APU by CPU cycles (interleave with CPU/PPU)."},
    {"write", (PyCFunction)nes_write, METH_VARARGS, "write(addr, value)"},
    {"read", (PyCFunction)nes_read, METH_VARARGS, "read(addr) — $4015 status"},
    {"samples_available", (PyCFunction)nes_samples_available, METH_NOARGS,
     "Number of float samples queued in the ring buffer."},
    {"irq_pending", (PyCFunction)nes_irq_pending, METH_NOARGS,
     "True if frame IRQ or DMC IRQ flag is set."},
    {"set_dmc_reader", (PyCFunction)nes_set_dmc_reader, METH_VARARGS,
     "set_dmc_reader(callable|None) — callable(addr) -> byte for DMC fetches."},
    {"drain_into", (PyCFunction)nes_drain_into, METH_VARARGS,
     "Copy queued samples into float32 buffer (zeros if underrun)."},
    {"render_into", (PyCFunction)nes_render_into, METH_VARARGS,
     "Offline: clock as needed and fill float32 mono buffer."},
    {NULL}
};

static PyTypeObject NesApuType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "rwt_rsound._chips.NesApuCore",
    .tp_basicsize = sizeof(NesApuObject),
    .tp_dealloc = (destructor)nes_dealloc,
    .tp_flags = Py_TPFLAGS_DEFAULT,
    .tp_doc = "NES APU (cycle-stepped; pulse/triangle/noise/DMC).",
    .tp_methods = nes_methods,
    .tp_getset = nes_getset,
    .tp_init = (initproc)nes_init,
    .tp_new = PyType_GenericNew,
};

int
rwt_nes_apu_add_to_module(PyObject *m)
{
    if (PyType_Ready(&NesApuType) < 0)
        return -1;
    Py_INCREF(&NesApuType);
    if (PyModule_AddObject(m, "NesApuCore", (PyObject *)&NesApuType) < 0) {
        Py_DECREF(&NesApuType);
        return -1;
    }
    if (PyModule_AddIntConstant(m, "NES_REGION_NTSC", NES_REGION_NTSC) < 0)
        return -1;
    if (PyModule_AddIntConstant(m, "NES_REGION_PAL", NES_REGION_PAL) < 0)
        return -1;
    if (PyModule_AddIntConstant(m, "NES_NTSC_CPU_HZ", 1789773) < 0)
        return -1;
    if (PyModule_AddIntConstant(m, "NES_PAL_CPU_HZ", 1662607) < 0)
        return -1;
    return 0;
}
