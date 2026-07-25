/*
 * Fast packed-pixel CP437 text blitter for 1 / 4 / 8 bpp row-major buffers.
 *
 * Layout matches rwt_rconsole.pixel_packing:
 *   8 bpp: 1 byte/pixel, pitch = width
 *   4 bpp: high nibble = left pixel, pitch = width/2
 *   1 bpp: MSB = leftmost pixel, pitch = width/8
 *
 * Glyphs: width 8, each scanline one byte, MSB = left. Font buffer is
 * 256 * glyph_h bytes (VGA ROM layout).
 */

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdint.h>
#include <string.h>

/* --- pixel write helpers ------------------------------------------------- */

static inline void
set_pixel_8(uint8_t *buf, int pitch, int x, int y, uint8_t color)
{
    buf[y * pitch + x] = color;
}

static inline void
set_pixel_4(uint8_t *buf, int pitch, int x, int y, uint8_t color)
{
    int i = y * pitch + (x >> 1);
    uint8_t existing = buf[i];
    color &= 0x0F;
    if ((x & 1) == 0)
        buf[i] = (uint8_t)((existing & 0x0F) | (color << 4));
    else
        buf[i] = (uint8_t)((existing & 0xF0) | color);
}

static inline void
set_pixel_1(uint8_t *buf, int pitch, int x, int y, uint8_t color)
{
    int i = y * pitch + (x >> 3);
    int bit = 7 - (x & 7);
    uint8_t mask = (uint8_t)(1u << bit);
    if (color & 1)
        buf[i] = (uint8_t)(buf[i] | mask);
    else
        buf[i] = (uint8_t)(buf[i] & (uint8_t)~mask);
}

/* --- core blit ----------------------------------------------------------- */

/*
 * Blit CP437 string into packed buffer.
 * bg < 0 means transparent (skip clear glyph bits).
 * Returns 0 on success, -1 with Python exception set on bad args.
 */
static int
blit_string_impl(
    uint8_t *dst,
    Py_ssize_t dst_len,
    int width,
    int height,
    int bpp,
    const uint8_t *font,
    int glyph_h,
    int x0,
    int y0,
    const uint8_t *text,
    Py_ssize_t text_len,
    int fg,
    int bg)
{
    int pitch;
    int max_color;
    Py_ssize_t expected;
    int cx, ch_i, row, col;
    int px, py;
    const uint8_t *glyph;
    uint8_t row_bits;
    int bit;
    int color;
    int transparent = (bg < 0);

    if (width <= 0 || height <= 0) {
        PyErr_SetString(PyExc_ValueError, "width and height must be positive");
        return -1;
    }
    if (glyph_h <= 0 || glyph_h > 64) {
        PyErr_SetString(PyExc_ValueError, "glyph_h out of range");
        return -1;
    }
    if (bpp == 8) {
        pitch = width;
        max_color = 255;
    } else if (bpp == 4) {
        if (width & 1) {
            PyErr_SetString(PyExc_ValueError, "4 bpp requires even width");
            return -1;
        }
        pitch = width / 2;
        max_color = 15;
    } else if (bpp == 1) {
        if (width & 7) {
            PyErr_SetString(PyExc_ValueError, "1 bpp requires width divisible by 8");
            return -1;
        }
        pitch = width / 8;
        max_color = 1;
    } else {
        PyErr_SetString(PyExc_ValueError, "bit_depth must be 1, 4, or 8");
        return -1;
    }

    expected = (Py_ssize_t)pitch * (Py_ssize_t)height;
    if (dst_len < expected) {
        PyErr_Format(PyExc_ValueError,
                     "buffer too small: need %zd bytes, got %zd",
                     expected, dst_len);
        return -1;
    }

    if (fg < 0 || fg > max_color) {
        PyErr_Format(PyExc_ValueError, "fg must be 0..%d", max_color);
        return -1;
    }
    if (!transparent && (bg < 0 || bg > max_color)) {
        PyErr_Format(PyExc_ValueError, "bg must be 0..%d or transparent", max_color);
        return -1;
    }

    cx = x0;
    for (ch_i = 0; ch_i < (int)text_len; ch_i++) {
        glyph = font + ((int)text[ch_i] & 0xFF) * glyph_h;
        for (row = 0; row < glyph_h; row++) {
            py = y0 + row;
            if (py < 0 || py >= height)
                continue;
            row_bits = glyph[row];
            for (col = 0; col < 8; col++) {
                px = cx + col;
                if (px < 0 || px >= width)
                    continue;
                bit = row_bits & (uint8_t)(0x80u >> col);
                if (bit)
                    color = fg;
                else if (transparent)
                    continue;
                else
                    color = bg;

                if (bpp == 8)
                    set_pixel_8(dst, pitch, px, py, (uint8_t)color);
                else if (bpp == 4)
                    set_pixel_4(dst, pitch, px, py, (uint8_t)color);
                else
                    set_pixel_1(dst, pitch, px, py, (uint8_t)color);
            }
        }
        cx += 8; /* glyph width fixed at 8 */
    }
    return 0;
}

/* --- Python wrapper ------------------------------------------------------ */

static PyObject *
py_blit_string(PyObject *self, PyObject *args, PyObject *kwargs)
{
    static char *kwlist[] = {
        "dst", "width", "height", "bit_depth",
        "font", "glyph_h",
        "x", "y", "text",
        "fg", "bg",
        NULL
    };
    Py_buffer dst_view;
    Py_buffer font_view;
    Py_buffer text_view;
    int width, height, bit_depth, glyph_h, x, y, fg, bg;
    int ok;

    dst_view.buf = NULL;
    font_view.buf = NULL;
    text_view.buf = NULL;

    /* bg default -1 (transparent) when omitted */
    bg = -1;
    if (!PyArg_ParseTupleAndKeywords(
            args, kwargs,
            "y*iiiy*iiiy*i|i:blit_string",
            kwlist,
            &dst_view, &width, &height, &bit_depth,
            &font_view, &glyph_h,
            &x, &y, &text_view,
            &fg, &bg)) {
        return NULL;
    }

    if (font_view.len < (Py_ssize_t)256 * glyph_h) {
        PyErr_Format(PyExc_ValueError,
                     "font buffer too small: need %d bytes, got %zd",
                     256 * glyph_h, font_view.len);
        ok = -1;
        goto done;
    }
    if (dst_view.readonly) {
        PyErr_SetString(PyExc_BufferError, "dst buffer must be writable");
        ok = -1;
        goto done;
    }

    ok = blit_string_impl(
        (uint8_t *)dst_view.buf,
        dst_view.len,
        width, height, bit_depth,
        (const uint8_t *)font_view.buf,
        glyph_h,
        x, y,
        (const uint8_t *)text_view.buf,
        text_view.len,
        fg, bg);

done:
    PyBuffer_Release(&dst_view);
    PyBuffer_Release(&font_view);
    PyBuffer_Release(&text_view);
    if (ok != 0)
        return NULL;
    Py_RETURN_NONE;
}

static PyMethodDef module_methods[] = {
    {"blit_string", (PyCFunction)py_blit_string,
     METH_VARARGS | METH_KEYWORDS,
     "blit_string(dst, width, height, bit_depth, font, glyph_h, x, y, text, fg, bg=-1)\n"
     "\n"
     "Blit a CP437 string into a packed paletted buffer.\n"
     "bg=-1 means transparent (glyph 0-bits are not written).\n"},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef moduledef = {
    PyModuleDef_HEAD_INIT,
    .m_name = "_blit",
    .m_doc = "Packed-pixel CP437 text blitter (1/4/8 bpp).",
    .m_size = -1,
    .m_methods = module_methods,
};

PyMODINIT_FUNC
PyInit__blit(void)
{
    return PyModule_Create(&moduledef);
}
