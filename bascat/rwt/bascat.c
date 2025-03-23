#include <Python.h>
#include<stdint.h>

static void unprotect(uint8_t *src, size_t len) {
    static const int KEY13[] = {0xA9, 0x84, 0x8D, 0xCD, 0x75, 0x83, 0x43, 0x63, 0x24, 0x83, 0x19, 0xF7, 0x9A};
    static const int KEY11[] = {0x1E, 0x1D, 0xC4, 0x77, 0x26, 0x97, 0xE0, 0x74, 0x59, 0x88, 0x7C};
    int idx13 = 0, idx11 = 0, ans;

    src[0] = 0xFF; // Mark as unprotected
    for (size_t idx = 1; idx < len; idx++) {
        ans = src[idx] & 0xFF;
        ans -= 11 - idx11;
        ans ^= KEY11[idx11];
        ans ^= KEY13[idx13];
        ans += 13 - idx13;
        src[idx] = (uint8_t)(ans & 0xFF);

        idx11 = (idx11 + 1) % 11;
        idx13 = (idx13 + 1) % 13;
    }
}

// BasicFile structure -- exists just to be iterable
typedef struct {
    PyObject_HEAD
    uint8_t *buffer;  // The GW-BASIC file data
    size_t len;             // Length of the buffer
} BasicFile;

// BascatIterator structure
typedef struct {
    PyObject_HEAD
    BasicFile *basic_file;  // Reference to the BasicFile object
    size_t pos;             // Current position in the buffer
} BascatIterator;

static int basicfile_init(PyObject* self, PyObject* args, PyObject* kw) {
    BasicFile* const s = (BasicFile*)self;
    Py_buffer pybuf;
    if (!PyArg_ParseTuple(args, "y*:BasicFile", &pybuf)) return -1; 

    // Make a copy of the buffer since we may need to modify it
    s->len = pybuf.len;
    s->buffer = (uint8_t *)malloc(pybuf.len);
    if (!s->buffer) {
        PyBuffer_Release(&pybuf);
        PyErr_NoMemory();
        return -1;
    }
    memcpy(s->buffer, pybuf.buf, pybuf.len);
    PyBuffer_Release(&pybuf);

    // Unprotect if necessary
    if ((s->len > 0) && (s->buffer[0] == 0xFE)) {
        unprotect(s->buffer, s->len);
    } else if ( (s->len == 0) || (s->buffer[0] != 0xFF)) {
        free(s->buffer);
        PyErr_SetString(PyExc_ValueError, "Bad first byte!");
        return -1; 
    }
    return 0;
}

static void basicfile_dealloc(BasicFile *self) {
    free(self->buffer);
    Py_TYPE(self)->tp_free((PyObject *)self);
}

static PyObject *basicfile_iter(PyObject *self); // forward declare

static PyTypeObject BasicFileType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "bascat.BasicFile",   
    .tp_doc = "A GWBASIC/BASICA tokenized file",
    .tp_basicsize = sizeof(BasicFile),   
    .tp_itemsize = 0,                        
    .tp_flags = Py_TPFLAGS_DEFAULT,    
    .tp_new = PyType_GenericNew,
    .tp_init = (initproc)basicfile_init,
    .tp_dealloc = (destructor)basicfile_dealloc,       
    .tp_iter = basicfile_iter,      
};

static void bascat_dealloc(BascatIterator *self) {
    Py_DECREF(self->basic_file);  // Decrease the reference count of the BasicFile object
    Py_TYPE(self)->tp_free((PyObject *)self);
}

static PyObject *bascat_next(PyObject *self); // forward declare

static PyObject *bascat_iter(PyObject *self) {
    Py_INCREF(self);
    return self;
}

static PyTypeObject BascatIteratorType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "bascat._BascatIterator",   
    .tp_doc = "An Iterator for GWBASIC/BASICA code lines",
    .tp_basicsize = sizeof(BascatIterator),   
    .tp_itemsize = 0,                        
    .tp_flags = Py_TPFLAGS_DEFAULT,    
    .tp_dealloc = (destructor)bascat_dealloc,       
    .tp_iter = bascat_iter,      
    .tp_iternext = bascat_next,      
};

static double mbf32_to_double(const uint8_t *buf) {
    uint32_t mbf = *(uint32_t *)buf; // Little-endian assumed
    if ((mbf & 0xFF000000) == 0) return 0.0;
    int sign = (mbf & 0x00800000) ? -1 : 1;
    int exp = ((mbf >> 24) & 0xFF) - 129;
    uint32_t mantissa = (mbf & 0x007FFFFF) | 0x00800000;
    double mant = (double)mantissa / (1 << 23);
    return sign * mant * pow(2.0, exp);
}

static double mbf64_to_double(const uint8_t *buf) {
    uint64_t mbf = *(uint64_t *)buf;
    if ((mbf & 0xFF00000000000000ULL) == 0) return 0.0;
    int sign = (mbf & 0x0080000000000000ULL) ? -1 : 1;
    int exp = ((mbf >> 56) & 0xFF) - 129;
    uint64_t mantissa = (mbf & 0x007FFFFFFFFFFFFFULL) | 0x0080000000000000ULL;
    double mant = (double)mantissa / (1ULL << 55);
    return sign * mant * pow(2.0, exp);
}

static const char *get_token_string(int code) {
    if (code >= 0x11 && code <= 0x1B) {
        static const char *nums[] = {"0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"};
        return nums[code - 0x11];
    } else if (code >= 0x81 && code <= 0xF4) {
        static const char *tokens1[] = {
            "END", "FOR", "NEXT", "DATA", "INPUT", "DIM", "READ", "LET", "GOTO", "RUN",
            "IF", "RESTORE", "GOSUB", "RETURN", "REM", "STOP", "PRINT", "CLEAR", "LIST",
            "NEW", "ON", "WAIT", "DEF", "POKE", "CONT", "<0x9A!>", "<0x9B!>", "OUT",
            "LPRINT", "LLIST", "<0x9F!>", "WIDTH", "ELSE", "TRON", "TROFF", "SWAP",
            "ERASE", "EDIT", "ERROR", "RESUME", "DELETE", "AUTO", "RENUM", "DEFSTR",
            "DEFINT", "DEFSNG", "DEFDBL", "LINE", "WHILE", "WEND", "CALL", "<0xB4!>",
            "<0xB5!>", "<0xB6!>", "WRITE", "OPTION", "RANDOMIZE", "OPEN", "CLOSE",
            "LOAD", "MERGE", "SAVE", "COLOR", "CLS", "MOTOR", "BSAVE", "BLOAD",
            "SOUND", "BEEP", "PSET", "PRESET", "SCREEN", "KEY", "LOCATE", "<0xCB!>",
            "TO", "THEN", "TAB(", "STEP", "USR", "FN", "SPC(", "NOT", "ERL", "ERR",
            "STRING$", "USING", "INSTR", "'", "VARPTR", "CSRLIN", "POINT", "OFF",
            "INKEY$", "<0xDF!>", "<0xE0!>", "<0xE1!>", "<0xE2!>", "<0xE3!>", "<0xE4!>",
            "<0xE5!>", ">", "=", "<", "+", "-", "*", "/", "^", "AND", "OR", "XOR",
            "EQV", "IMP", "MOD", "\\"
        };
        return tokens1[code - 0x81];
    } else if (code >= 0xFD81 && code <= 0xFD8B) {
        static const char *tokens2[] = {"CVI", "CVS", "CVD", "MKI$", "MKS$", "MKD$", "<0xFD87!>", "<0xFD88!>", "<0xFD89!>", "<0xFD8A!>", "EXTERR"};
        return tokens2[code - 0xFD81];
    } else if (code >= 0xFE81 && code <= 0xFEA8) {
        static const char *tokens3[] = {
            "FILES", "FIELD", "SYSTEM", "NAME", "LSET", "RSET", "KILL", "PUT", "GET",
            "RESET", "COMMON", "CHAIN", "DATE$", "TIME$", "PAINT", "COM", "CIRCLE",
            "DRAW", "PLAY", "TIMER", "ERDEV", "IOCTL", "CHDIR", "MKDIR", "RMDIR",
            "SHELL", "ENVIRON", "VIEW", "WINDOW", "PMAP", "PALETTE", "LCOPY", "CALLS",
            "<0xFEA2!>", "<0xFEA3!>", "NOISE", "PCOPY", "TERM", "LOCK", "UNLOCK"
        };
        return tokens3[code - 0xFE81];
    } else if (code >= 0xFF81 && code <= 0xFFA5) {
        static const char *tokens4[] = {
            "LEFT$", "RIGHT$", "MID$", "SGN", "INT", "ABS", "SQR", "RND", "SIN",
            "LOG", "EXP", "COS", "TAN", "ATN", "FRE", "INP", "POS", "LEN", "STR$",
            "VAL", "ASC", "CHR$", "PEEK", "SPACE$", "OCT$", "HEX$", "LPOS", "CINT",
            "CSNG", "CDBL", "FIX", "PEN", "STICK", "STRIG", "EOF", "LOC", "LOF"
        };
        return tokens4[code - 0xFF81];
    }
    return NULL;
}

static PyObject *basicfile_iter(PyObject *self) {
    BasicFile *bf = (BasicFile *)self;
    BascatIterator *it = (BascatIterator *)PyObject_New(BascatIterator, &BascatIteratorType);
    if (!it) return NULL;
    it->basic_file = bf;
    Py_INCREF(bf);  // Keep the BasicFile alive
    it->pos = 1;  // Start after the first byte (0xFF)
    return (PyObject *)it;
}

static void append_str(char *str, size_t str_len, size_t *str_pos, const char *to_append) {
    size_t len = strlen(to_append);
    if (*str_pos + len < str_len) {
        memcpy(str + *str_pos, to_append, len);
        *str_pos += len;
    }
}

static int append_next_token(const unsigned char *buf, size_t len, size_t *pos, char *str, size_t str_len, size_t *str_pos) {
    if (*pos >= len) return 0;
    int nxt = buf[(*pos)++] & 0xFF;
    if (nxt >= 0xFD && *pos < len) {
        nxt = (nxt << 8) | (buf[(*pos)++] & 0xFF);
    }

    if (nxt == 0) return 0;

    char temp[32];
    const char *token;
    if (nxt == 0x3A) {
        if (*pos < len && buf[*pos] == 0xA1) {
            append_str(str, str_len, str_pos, "ELSE");
            (*pos)++;
        } else if (*pos + 1 < len && buf[*pos] == 0x8F && buf[*pos + 1] == 0xD9) {
            append_str(str, str_len, str_pos, "'");
            *pos += 2;
        } else {
            append_str(str, str_len, str_pos, ":");
        }
    } else if (nxt == 0xB1) {
        append_str(str, str_len, str_pos, "WHILE");
        if (*pos < len && buf[*pos] == 0xE9) (*pos)++;
    } else if (nxt >= 0x20 && nxt <= 0x7E) {
        if (*str_pos < str_len - 1) str[(*str_pos)++] = (char)nxt;
    } else if ( (token = get_token_string(nxt)) ) {
        append_str(str, str_len, str_pos, token);
    } else {
        switch (nxt) {
            case 0x0B: // Octal short
                if (*pos + 1 >= len) return 0;
                sprintf(temp, "&O%o", *(uint16_t *)(buf + *pos));
                append_str(str, str_len, str_pos, temp);
                *pos += 2;
                break;
            case 0x0C: // Hex short
                if (*pos + 1 >= len) return 0;
                sprintf(temp, "&H%X", *(uint16_t *)(buf + *pos));
                append_str(str, str_len, str_pos, temp);
                *pos += 2;
                break;
            case 0x0E: // Unsigned short
                if (*pos + 1 >= len) return 0;
                sprintf(temp, "%u", *(uint16_t *)(buf + *pos));
                append_str(str, str_len, str_pos, temp);
                *pos += 2;
                break;
            case 0x0F: // Unsigned byte
                if (*pos >= len) return 0;
                sprintf(temp, "%u", buf[*pos] & 0xFF);
                append_str(str, str_len, str_pos, temp);
                (*pos)++;
                break;
            case 0x1C: // Signed short
                if (*pos + 1 >= len) return 0;
                sprintf(temp, "%d", *(int16_t *)(buf + *pos));
                append_str(str, str_len, str_pos, temp);
                *pos += 2;
                break;
            case 0x1D: // MBF 32-bit float
                if (*pos + 3 >= len) return 0;
                sprintf(temp, "%g", mbf32_to_double(buf + *pos));
                append_str(str, str_len, str_pos, temp);
                *pos += 4;
                break;
            case 0x1F: // MBF 64-bit float
                if (*pos + 7 >= len) return 0;
                sprintf(temp, "%g", mbf64_to_double(buf + *pos));
                append_str(str, str_len, str_pos, temp);
                *pos += 8;
                break;
            default:
                sprintf(temp, "<UNK! %x>", nxt);
                append_str(str, str_len, str_pos, temp);
        }
    }
    return 1;
}

static PyObject *bascat_next(PyObject *self) {
    BascatIterator *it = (BascatIterator *)self;
    BasicFile *bf = it->basic_file;
    if (it->pos + 1 >= bf->len) return NULL; // End of buffer

    // Read line number (little-endian short)
    uint16_t line_num = *(uint16_t *)(bf->buffer + it->pos);
    it->pos += 2;
    if (line_num == 0) return NULL; // End of file

    // Build the line string
    char line[4096] = {0}; // Assume 4KB is enough per line
    size_t str_pos = 0;
    sprintf(line, "%u  ", line_num);
    str_pos = strlen(line);

    while (append_next_token(bf->buffer, bf->len, &it->pos, line, sizeof(line), &str_pos)) {
        // Continue until end of line
    }
    line[str_pos] = '\0';

    return PyUnicode_FromString(line);
}

#if  0
// Method definitions
static PyMethodDef BascatMethods[] = {
    {"process", bascat_process, METH_VARARGS, "Process a GW-BASIC file buffer and return an iterator."},
    {NULL, NULL, 0, NULL}
};
#endif

// Module definition
static struct PyModuleDef bascatmodule = {
    PyModuleDef_HEAD_INIT,
    "bascat",
    "Module to process GW-BASIC files.",
    -1,
    NULL, NULL, NULL, NULL, NULL
};

// Module initialization
PyMODINIT_FUNC PyInit_bascat(void) {
    PyObject *m;
    if ((PyType_Ready(&BasicFileType) < 0)  ||
        (PyType_Ready(&BascatIteratorType) < 0)) return NULL;
    m = PyModule_Create(&bascatmodule);
    if (m == NULL) return NULL;
    Py_INCREF(&BasicFileType);
    Py_INCREF(&BascatIteratorType);
    if (PyModule_AddObject(m, "BasicFile", (PyObject *)&BasicFileType) < 0) goto error2;
    if (PyModule_AddObject(m, "_BascatIterator", (PyObject *)&BascatIteratorType) < 0) goto error2;
    return m;
error2:
    Py_DECREF(&BasicFileType);
    Py_DECREF(&BascatIteratorType);
    Py_DECREF(m);
    return NULL;
}

