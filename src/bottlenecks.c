/*
 *  This file is part of Bakefile (http://www.bakefile.org)
 *
 *  Copyright (C) 2003-2007 Vaclav Slavik
 *
 *  Permission is hereby granted, free of charge, to any person obtaining a
 *  copy of this software and associated documentation files (the "Software"),
 *  to deal in the Software without restriction, including without limitation
 *  the rights to use, copy, modify, merge, publish, distribute, sublicense,
 *  and/or sell copies of the Software, and to permit persons to whom the
 *  Software is furnished to do so, subject to the following conditions:
 *
 *  The above copyright notice and this permission notice shall be included in
 *  all copies or substantial portions of the Software.
 *
 *  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 *  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 *  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 *  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 *  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
 *  FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
 *  DEALINGS IN THE SOFTWARE.
 *
 *  $Id$
 *
 *  Assorted routines that were too slow when implemented in Python are
 *  implemented in C here for better performance.
 *
 */

#include <Python.h>
#include <string.h>
#include <assert.h>

/* ------------------------------------------------------------------------ */
/*                     Text buffers used for evaluations                    */
/* ------------------------------------------------------------------------ */

#define TEXTBUF_COUNT                8
#define TEXTBUF_SIZE            102400

static char *textbuf[TEXTBUF_COUNT] = 
        {NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL};
static unsigned textbufSize[TEXTBUF_COUNT] = 
        {0,0,0,0,0,0,0,0};
static int textbufCurrent = -1;

#define ENSURE_BUFFER(size) \
    { \
        if (TEXTBUF_SIZE < size + 1) \
        { \
            PyErr_SetString(PyExc_RuntimeError, \
       "bottlenecks.doEvalExpr: too large variables, increase TEXTBUF_SIZE"); \
            return NULL; \
        } \
    }

/* safety checks against re-entrancy (shouldn't ever happen): */
#define ACQUIRE_BUFFER() \
    { \
        if (++textbufCurrent >= TEXTBUF_COUNT) \
        { \
            PyErr_SetString(PyExc_RuntimeError, \
                            "bottlenecks.doEvalExpr: recursion too deep"); \
            return NULL; \
        } \
        if (textbuf[textbufCurrent] == NULL) \
            textbuf[textbufCurrent] = malloc(TEXTBUF_SIZE); \
    }
#define RELEASE_BUFFER() \
    textbufCurrent--


/* ------------------------------------------------------------------------ */
/*                          Expressions evaluation                          */
/* ------------------------------------------------------------------------ */

const char *doEvalExpr(const char *expr,
                       PyObject *varCallb,
                       PyObject *textCallb,
                       PyObject *moreArgs,
                       PyObject *use_options,
                       PyObject *target,
                       PyObject *add_dict)
{
    int len = strlen(expr);
    int i;
    char *output, *txtbuf;
    const char *text_begin, *code_begin;
    unsigned brackets = 0;
    const char *origexpr = expr;

    ACQUIRE_BUFFER();
    ENSURE_BUFFER(len);
    output = txtbuf = textbuf[textbufCurrent];

    i = 0;
    text_begin = expr;
    while (i < len - 1)
    {
        if (*expr == '$' && *(expr + 1) == '(')
        {
            unsigned textlen = expr - text_begin;
            if (textlen)
            {
                if (textCallb == Py_None)
                {
                    ENSURE_BUFFER(output - txtbuf + textlen);
                    memcpy(output, text_begin, textlen);
                    output += textlen;
                }
                else
                {
                    int size;
                    PyObject *r =
                        PyObject_CallFunction(textCallb,
                                              "Os#",
                                              moreArgs, text_begin, textlen);
                    if (PyErr_Occurred())
                    {
                        RELEASE_BUFFER();
                        return NULL;
                    }
                    size = PyString_Size(r);
                    ENSURE_BUFFER(output - txtbuf + size);
                    memcpy(output, PyString_AsString(r), size);
                    output += size;
                    Py_DECREF(r);
                }
            }

            expr += 2;
            i += 2;
            brackets = 1;
            code_begin = expr;

            while (i < len)
            {
                if (*expr == ')')
                {
                    if (--brackets == 0)
                    {
                        int size;
                        PyObject *r =
                            PyObject_CallFunction(varCallb,
                                                  "Os#OOO",
                                                  moreArgs,
                                                  code_begin,
                                                  expr - code_begin,
                                                  use_options,
                                                  target,
                                                  add_dict);
                        if (PyErr_Occurred())
                        {
                            RELEASE_BUFFER();
                            return NULL;
                        }
                        size = PyString_Size(r);
                        ENSURE_BUFFER(output - txtbuf + size);
                        memcpy(output, PyString_AsString(r), size);
                        output += size;
                        Py_DECREF(r);
                        break;
                    }
                }
                else if (*expr == '(')
                {
                    brackets++;
                }
                else if (*expr == '\'' || *expr == '"')
                {
                    char what = *expr;
                    while (i < len)
                    {
                        i++;
                        expr++;
                        if (*expr == what)
                            break;
                    }
                }
                i++;
                expr++;
            }

            text_begin = expr + 1;
        }
        i++;
        expr++;
    }

    if (brackets > 0)
    {
        PyErr_Format(PyExc_RuntimeError,
                     "unmatched brackets in '%s'", origexpr);
        return NULL;
    }

    if (expr - text_begin >= 0)
    {
        if (textCallb == Py_None)
        {
            ENSURE_BUFFER(len + output - txtbuf);
            strcpy(output, text_begin);
            output += expr - text_begin + 1;
        }
        else
        {
            PyObject *r;
            unsigned textlen;
            int size;
            textlen = strlen(text_begin);
            r = PyObject_CallFunction(textCallb,
                                      "Os#",
                                      moreArgs, text_begin, textlen);
            if (PyErr_Occurred())
            {
                RELEASE_BUFFER();
                return NULL;
            }
            size = PyString_Size(r);
            ENSURE_BUFFER(output - txtbuf + size);
            memcpy(output, PyString_AsString(r), size);
            output += size;
            Py_DECREF(r);
        }
    }
    *output = 0;

    RELEASE_BUFFER();

    return txtbuf;
}

/*

Original Python code for reference:

def __doEvalExpr(e, varCallb, textCallb, moreArgs,
                 use_options=1, target=None, add_dict=None):
    if textCallb == None:
        textCallb = lambda y,x: x
    lng = len(e)
    i = 0
    brackets = 0
    txt = ''
    output = ''
    while i < lng-1:
        if e[i] == '$' and e[i+1] == '(':
            if txt != '':
                output += textCallb(moreArgs, txt)
            txt = ''
            code = ''
            i += 2
            brackets = 1
            while i < lng:
                if e[i] == ')':
                    brackets -= 1
                    if brackets == 0:
                        output += varCallb(moreArgs,
                                           code, use_options, target, add_dict)
                        break
                    else:
                        code += e[i]
                elif e[i] == '(':
                    brackets += 1
                    code += e[i]
                elif e[i] == "'" or e[i] == '"':
                    what = e[i]
                    code += e[i]
                    while i < lng:
                        i += 1
                        code += e[i]
                        if e[i] == what: break
                else:
                    code += e[i]
                i += 1
        else:
            txt += e[i]
        i += 1

    if brackets > 0:
        raise RuntimeError("unmatched brackets in '%s'" % expr)

    output += textCallb(moreArgs, txt + e[i:])
    return output

*/


/* ------------------------------------------------------------------------ */
/*                     Fast merged dictionaries support                     */
/* ------------------------------------------------------------------------ */

#if PY_VERSION_HEX < 0x02040000

/* NB: see bottlenecks.i for high-level explanation. The way the hijacking
       is implemented is by replacing PyDictObject::ma_lookup pointer with
       our function. This pointer is used to do *all* lookups in PyDictObject
       (i.e. not only PyDict_GetItem) so this can *badly* screw things up
       if we're not extremely careful in what we're doing! */

/* Max number of proxied dictionaries */
#define MAX_PROXY_DICTS

typedef struct _ProxySlave
{
    PyDictObject *dict;
    struct _ProxySlave *next;
} ProxySlave;

typedef struct _ProxyDictData
{
    PyDictEntry *(*ma_lookup_orig)(PyDictObject *mp, PyObject *key, long hash);
    PyObject *dict;
    ProxySlave *slaves;
    struct _ProxyDictData *next;
} ProxyDictData;

static ProxyDictData *gs_proxyDict = NULL;

static PyDictEntry *proxydict_ma_lookup(PyDictObject *mp,
                                        PyObject *key,
                                        long hash)
{
    ProxyDictData *data;

    for (data = gs_proxyDict; data; data = data->next)
    {
        if ((PyDictObject*)data->dict == mp)
        {
            ProxySlave *slave;
            PyDictEntry *ret;
            for (slave = data->slaves; slave; slave = slave->next)
            {
                ret = slave->dict->ma_lookup(slave->dict, key, hash);
                if (ret->me_value)
                    return ret;
            }
            /* this will fail, but it will return NULL entry of the right
               dictionary instance: */
            return data->ma_lookup_orig(mp, key, hash);
        }
    }
    assert(0);
}

void proxydict_release(void *d)
{
    ProxyDictData *data = (ProxyDictData*)d;
    if (data->dict)
    {
        ProxySlave *s, *s2;
        for (s = data->slaves; s; s = s2)
        {
            s2 = s->next;
            Py_DECREF(s->dict);
            free(s);
        }
        ((PyDictObject*)data->dict)->ma_lookup = data->ma_lookup_orig;
        Py_DECREF(data->dict);
    }

    if (gs_proxyDict == data)
    {
        gs_proxyDict = data->next;
    }
    else
    {
        ProxyDictData *d;
        for (d = gs_proxyDict; d; d = d->next)
        {
            if (d->next == data)
            {
                d->next = data->next;
                break;
            }
        }
    }

    free(data);
}

PyObject *proxydict_create(void)
{
    ProxyDictData *data = malloc(sizeof(ProxyDictData));
    data->ma_lookup_orig = NULL;
    data->dict = NULL;
    data->slaves = NULL;
    data->next = gs_proxyDict;
    gs_proxyDict = data;
    return PyCObject_FromVoidPtr(data, proxydict_release);
}

void proxydict_hijack(PyObject *data, PyObject *dict)
{
    PyDictObject *asdict = (PyDictObject*)dict;
    ProxyDictData *d = (ProxyDictData*)PyCObject_AsVoidPtr(data);
    d->dict = dict;
    d->ma_lookup_orig = asdict->ma_lookup;
    asdict->ma_lookup = proxydict_ma_lookup;
    Py_INCREF(dict);
}

void proxydict_add(PyObject *data, PyObject *dict)
{
    ProxySlave *slave;
    PyDictObject *asdict = (PyDictObject*)dict;
    ProxyDictData *d = (ProxyDictData*)PyCObject_AsVoidPtr(data);

    slave = malloc(sizeof(ProxySlave));
    slave->dict = asdict;
    slave->next = d->slaves;
    d->slaves = slave;
    Py_INCREF(dict);
}

#else /* Python>=2.4 */

/* not used with new Python versions, but SWIG won't let us compile this
   in only conditionally, so use empty stubs: */
void proxydict_release(void *d) {}
PyObject *proxydict_create(void) { return NULL; }
void proxydict_hijack(PyObject *data, PyObject *dict) {}
void proxydict_add(PyObject *data, PyObject *dict) {}

#endif /* Python<2.4 / Python>=2.4 */
