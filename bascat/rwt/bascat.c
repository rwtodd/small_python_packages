#include <Python.h>
#include<stdint.h>
#include<stdio.h>

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
    char *out_buffer;       // output buffer...
    size_t out_buffsz;      // size of output buffer...
} BascatIterator;

// ensure that the buffer always has at least 32 empty slots left...
static int ensure_size(BascatIterator *it, size_t pos) {
   if (it->out_buffsz < (pos + 32)) {
      it->out_buffsz += 128; 
      it->out_buffer = realloc(it->out_buffer, it->out_buffsz);
      if(it->out_buffer == NULL) return 0; // FALSE
   }
   return 1; // TRUE
}

static int basicfile_init(PyObject* self, PyObject* args, PyObject* kw) {
    BasicFile* const s = (BasicFile*)self;
    Py_buffer pybuf;
    if (!PyArg_ParseTuple(args, "y*:BasicFile", &pybuf)) return -1; 

    // Make a copy of the buffer since we may need to modify it
    s->len = pybuf.len;
    s->buffer = malloc(pybuf.len);
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
    free(self->out_buffer);
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
    uint32_t mbf = ((uint32_t)buf[0]) |
	    (((uint32_t)buf[1]) << 8) |
	    (((uint32_t)buf[2]) << 16) |
	    (((uint32_t)buf[3]) << 24);
    if ((mbf & 0xFF000000) == 0) return 0.0;
    int sign = (mbf & 0x00800000) ? -1 : 1;
    int exp = ((mbf >> 24) & 0xFF) - 129;
    uint32_t mantissa = (mbf & 0x007FFFFF) | 0x00800000;
    double mant = (double)mantissa / (1 << 23);
    return sign * mant * pow(2.0, exp);
}

static double mbf64_to_double(const uint8_t *buf) {
    uint64_t mbf = ((uint64_t)buf[0]) |
	    (((uint64_t)buf[1]) << 8) |
	    (((uint64_t)buf[2]) << 16) |
	    (((uint64_t)buf[3]) << 24) |
	    (((uint64_t)buf[4]) << 32) |
	    (((uint64_t)buf[5]) << 40) |
	    (((uint64_t)buf[6]) << 48) |
	    (((uint64_t)buf[7]) << 56);
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
    char *obuff = malloc(256);
    if(!obuff) return NULL;
    BasicFile *bf = (BasicFile *)self;
    BascatIterator *it = (BascatIterator *)PyObject_New(BascatIterator, &BascatIteratorType);
    if (!it) return NULL;
    it->basic_file = bf;
    Py_INCREF(bf);  // Keep the BasicFile alive
    it->pos = 1;  // Start after the first byte (0xFF)
    it->out_buffer = obuff;
    it->out_buffsz = 256;
    return (PyObject *)it;
}

static void append_str(char *dest, size_t *str_pos, const char *to_append) {
    size_t count = 0;
    dest = dest + *str_pos;
    while( (*dest++ = *to_append++) ) {
      ++count;
    }
    *str_pos += count;
}

#define read_u16_le()  ( (uint16_t)( (uint16_t)(buf[*pos]) | ((uint16_t)(buf[*pos+1]) << 8) ) )
#define read_i16_le()  ( (int16_t)( (uint16_t)(buf[*pos]) | ((uint16_t)(buf[*pos+1]) << 8) ) )
#define check_space(n) if ((*pos + (n)) > len) return 0

static int append_next_token(const uint8_t *buf, size_t len, size_t *pos, char *outbuff,  size_t *str_pos) {
    check_space(0);
    int nxt = buf[(*pos)++] & 0xFF;
    if (nxt >= 0xFD && *pos < len) {
        nxt = (nxt << 8) | (buf[(*pos)++] & 0xFF);
    }
    if (nxt == 0) return 0;

    const char *token;
    if (nxt == 0x3A) {
        if (*pos < len && buf[*pos] == 0xA1) {
            append_str(outbuff, str_pos, "ELSE");
            (*pos)++;
        } else if (*pos + 1 < len && buf[*pos] == 0x8F && buf[*pos + 1] == 0xD9) {
            append_str(outbuff, str_pos, "'");
            *pos += 2;
        } else {
            append_str(outbuff, str_pos, ":");
        }
    } else if (nxt == 0xB1) {
        append_str(outbuff, str_pos, "WHILE");
        if (*pos < len && buf[*pos] == 0xE9) (*pos)++;
    } else if (nxt >= 0x20 && nxt <= 0x7E) {
        outbuff[(*str_pos)++] = (char)nxt;
    } else if ( (token = get_token_string(nxt)) ) {
        append_str(outbuff, str_pos, token);
    } else {
        switch (nxt) {
            case 0x0B: // Octal short
		check_space(2);
                *str_pos += snprintf(outbuff + *str_pos, 32, "&O%o", read_u16_le()); 
                *pos += 2;
                break;
            case 0x0C: // Hex short
		check_space(2);
                *str_pos += snprintf(outbuff + *str_pos, 32, "&H%X", read_u16_le() ); 
                *pos += 2;
                break;
            case 0x0E: // Unsigned short
		check_space(2);
                *str_pos += snprintf(outbuff + *str_pos, 32, "%u", read_u16_le() );
                *pos += 2;
                break;
            case 0x0F: // Unsigned byte
		check_space(1);
                *str_pos += snprintf(outbuff + *str_pos, 32, "%u", buf[*pos] & 0xFF);
                (*pos)++;
                break;
            case 0x1C: // Signed short
		check_space(2);
                *str_pos += snprintf(outbuff + *str_pos, 32, "%d", read_i16_le() );
                *pos += 2;
                break;
            case 0x1D: // MBF 32-bit float
		check_space(4);
                *str_pos += snprintf(outbuff + *str_pos, 32, "%g", mbf32_to_double(buf + *pos));
                *pos += 4;
                break;
            case 0x1F: // MBF 64-bit float
		check_space(8);
                *str_pos += snprintf(outbuff + *str_pos, 32, "%g", mbf64_to_double(buf + *pos));
                *pos += 8;
                break;
            default:
                *str_pos += snprintf(outbuff + *str_pos, 32, "<UNK! %x>", nxt);
        }
    }
    return 1;
}
#undef read_u16_le
#undef read_i16_le

#define read_u16_le() ((uint16_t)( (uint16_t)(bf->buffer[it->pos]) | ((uint16_t)(bf->buffer[it->pos+1]) << 8)))

static PyObject *bascat_next(PyObject *self) {
    BascatIterator *it = (BascatIterator *)self;
    BasicFile *bf = it->basic_file;
    if ((it->pos + 4) >= bf->len) return NULL; // End of buffer

    // read the link...
    if( read_u16_le() == 0 ) return NULL;
    it->pos += 2;

    // Read line number (little-endian short)
    uint16_t line_num = read_u16_le(); 
    it->pos += 2;

    // Build the line string
    size_t str_pos = 0;
    str_pos = snprintf(it->out_buffer, 32, "%u  ", line_num);

    while (append_next_token(bf->buffer, bf->len, &it->pos, it->out_buffer, &str_pos)) {
	if(!ensure_size(it, str_pos)) {
	  return NULL;
	}
    }
    it->out_buffer[str_pos] = '\0';

    return PyUnicode_FromString(it->out_buffer);
}
#undef read_u16_le

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

