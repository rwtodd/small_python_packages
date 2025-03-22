#include <Python.h>
#include<stdint.h>

// Define a struct for the BufferSummer object to hold instance data
typedef struct {
    PyObject_HEAD
    uint8_t i, j, k, z, a, w;
    uint8_t mem[256];
} SpritzState;

static int spritzkernel_init(PyObject* self, PyObject* args, PyObject* kw) {
    SpritzState* const s = (SpritzState*)self;

    // Ensure no arguments are passed
    if (!PyArg_ParseTuple(args, ":SpritzKernel")) {
        return -1;
    }

    // Initialize the spritz state
    s->i = s->j = s->k = s->z = s->a = 0;
    s->w = 1;
    for (int idx = 0; idx < 256; ++idx) s->mem[idx] = idx;      
    return 0;
}

PyObject *
spritz_reset(PyObject * self) {
    SpritzState* const s = (SpritzState*)self;
    // Initialize the spritz state
    s->i = s->j = s->k = s->z = s->a = 0;
    s->w = 1;
    for (int idx = 0; idx < 256; ++idx) s->mem[idx] = idx;      

    Py_INCREF(Py_None);  // Increment refcount since we're returning it
    return Py_None;  
}

static void spritzkernel_dealloc(SpritzState* self) {
    // No additional cleanup needed for running_sum (it's just an integer)
    Py_TYPE(self)->tp_free((PyObject*)self);
}

static inline void
swap (uint8_t * const arr, size_t el1, size_t el2)
{
  uint8_t tmp = arr[el1];
  arr[el1] = arr[el2];
  arr[el2] = tmp;
}

/* when adding indices... need them modulus 256 */
#define smem(x)  s->mem[ (x) & 0xff ]

static void
update (SpritzState *const s, int times)
{
  uint8_t mi = s->i;
  uint8_t mj = s->j;
  uint8_t mk = s->k;
  const uint8_t mw = s->w;

  while (times--)
    {
      mi += mw;
      mj = mk + smem (mj + s->mem[mi]);
      mk = mi + mk + s->mem[mj];
      swap (s->mem, mi, mj);
    }

  s->i = mi;
  s->j = mj;
  s->k = mk;
}


static void
whip (SpritzState *const s, const int amt)
{
  update (s, amt);
  s->w += 2;
}

static void
crush (SpritzState *const s)
{
  for (size_t v = 0; v < (256 / 2); ++v)
    {
      if (s->mem[v] > s->mem[256 - 1 - v])
        swap (s->mem, v, 256 - 1 - v);
    }
}

static void
shuffle (SpritzState *const s)
{
  whip (s, 256 * 2);
  crush (s);
  whip (s, 256 * 2);
  crush (s);
  whip (s, 256 * 2);
  s->a = 0;
}

static inline void
absorb_nibble (SpritzState *const s, uint8_t x)
{
  if (s->a == 256 / 2)
    shuffle (s);
  swap (s->mem, s->a, (256 / 2 + x));
  s->a++;
}

static inline void
spritz_absorb (SpritzState *const s, const uint8_t b)
{
  absorb_nibble (s, b & 0x0f);
  absorb_nibble (s, b >> 4);
}

PyObject *
spritz_absorb_many (PyObject *self, PyObject *buffer)
{
  SpritzState* const s = (SpritzState*)self;
  Py_buffer pybuf;

  // Get the buffer
  if (PyObject_GetBuffer(buffer, &pybuf, PyBUF_SIMPLE) != 0) {
      return NULL;  // Error set by PyObject_GetBuffer
  }
  
  uint8_t * bytes = (uint8_t *)pybuf.buf;
  const uint8_t *const end = bytes + pybuf.len;
  while (bytes != end) {
    spritz_absorb (s, *bytes++);
  }
  PyBuffer_Release(&pybuf);

  Py_INCREF(Py_None);  // Increment refcount since we're returning it
  return Py_None;
}

PyObject *
spritz_absorb_stop (PyObject *self)
{
  SpritzState* const s = (SpritzState*)self;
  if (s->a == 256 / 2)
    shuffle (s);
  s->a++;

  Py_INCREF(Py_None);  // Increment refcount since we're returning it
  return Py_None;
}

static uint8_t
drip_one (SpritzState *const s)
{
  update (s, 1);
  s->z = smem (s->j + smem (s->i + smem (s->z + s->k)));
  return s->z;
}

PyObject *
spritz_drip (PyObject *self)
{
  SpritzState* const s = (SpritzState*)self;
  if (s->a > 0)
    shuffle (s);
  return PyLong_FromLong(drip_one(s));
}

PyObject *
spritz_drip_many (PyObject *self, PyObject *buffer)
{
  SpritzState* const s = (SpritzState*)self;
  Py_buffer pybuf;

  // Get the buffer
  if (PyObject_GetBuffer(buffer, &pybuf, PyBUF_WRITABLE) < 0) {
    PyErr_SetString(PyExc_TypeError, "buffer must be writable");
    return NULL;
  }
  
  uint8_t * bytes = (uint8_t *)pybuf.buf;
  const uint8_t *const end = bytes + pybuf.len;

  if (s->a > 0)
    shuffle (s);

  while (bytes != end) {
    *bytes++ = drip_one (s);    
  }
  PyBuffer_Release(&pybuf);

  Py_INCREF(Py_None);  // Increment refcount since we're returning it
  return Py_None;
}

PyObject *
spritz_xor_many (PyObject *self, PyObject *buffer)
{
  SpritzState* const s = (SpritzState*)self;
  Py_buffer pybuf;

  // Get the buffer
  if (PyObject_GetBuffer(buffer, &pybuf, PyBUF_WRITABLE) < 0) {
    PyErr_SetString(PyExc_TypeError, "buffer must be writable");
    return NULL;
  }
  
  uint8_t * bytes = (uint8_t *)pybuf.buf;
  const uint8_t *const end = bytes + pybuf.len;

  if (s->a > 0)
    shuffle (s);

  while (bytes != end) {
    *bytes++ ^= drip_one (s);    
  }
  PyBuffer_Release(&pybuf);

  Py_INCREF(Py_None);  // Increment refcount since we're returning it
  return Py_None;
}

/* absorb_number is a helper function which absorbs the bytes
 * of a number, one at a time.  Used as part of the hashing
 * process for large hash sizes.
 */
PyObject *
spritz_absorb_number (PyObject * self, PyObject *num)
{
  SpritzState* const s = (SpritzState*)self;
  uint32_t number = (uint32_t)PyLong_AsLong(num);
  if (PyErr_Occurred()) {
    return NULL;  // Return NULL if conversion fails (e.g., not an int or overflow)
  }

  do {
    spritz_absorb (s, (uint8_t) (number & 0xff));
    number = number >> 8;
  } while(number > 0);

  Py_INCREF(Py_None);  // Increment refcount since we're returning it
  return Py_None;
}

static PyMethodDef spritzkernel_methods[] = {
  {"absorb", (PyCFunction)spritz_absorb_many, METH_O, "absorb the bytes of a buffer into the kernel"},
  {"absorb_number", (PyCFunction)spritz_absorb_number, METH_O, "absorb the bytes of an integer into the kernel"},
  {"absorb_stop", (PyCFunction)spritz_absorb_stop, METH_NOARGS, "absorb a special 'stop' dividing token"},
  {"drip_byte", (PyCFunction)spritz_drip, METH_NOARGS, "extract a single byte from the kernel"},
  {"drip", (PyCFunction)spritz_drip_many, METH_O, "extract bytes from the kernel into the buffer"},
  {"xor", (PyCFunction)spritz_xor_many, METH_O, "extract bytes from the kernel and xor them into the buffer"},
  {"reset", (PyCFunction)spritz_reset, METH_NOARGS, "reset the kernel to a fresh state"},
  {NULL, NULL, 0, NULL}  // Sentinel
};

static PyTypeObject SpritzKernelType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "rwt.spritz._internal.SpritzKernel", 
    .tp_doc = "A class to maintain a the status of a spritz sponge",
    .tp_basicsize = sizeof(SpritzState),  // Size includes running_sum
    .tp_itemsize = 0,
    .tp_flags = Py_TPFLAGS_DEFAULT,
    .tp_new = PyType_GenericNew,
    .tp_init = (initproc)spritzkernel_init,
    .tp_dealloc = (destructor)spritzkernel_dealloc,
    .tp_methods = spritzkernel_methods,
};

static struct PyModuleDef mymodulemodule = {
    PyModuleDef_HEAD_INIT,
    "_internal",          // Module name
    "Module with a SpritzKernel class",
    -1,
    NULL, NULL, NULL, NULL, NULL
};

PyMODINIT_FUNC PyInit__internal(void) {
    PyObject* m;

    if (PyType_Ready(&SpritzKernelType) < 0) {
        return NULL;
    }

    m = PyModule_Create(&mymodulemodule);
    if (m == NULL) {
        return NULL;
    }

    Py_INCREF(&SpritzKernelType);
    if (PyModule_AddObject(m, "SpritzKernel", (PyObject*)&SpritzKernelType) < 0) {
        Py_DECREF(&SpritzKernelType);
        Py_DECREF(m);
        return NULL;
    }

    return m;
}
