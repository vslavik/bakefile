/*
 *  Assorted routines that were too slow when implemented in Python are
 *  implemented in C here for better performance.
 *
 *  $Id$
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
    unsigned braces;
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
            braces = 1;
            code_begin = expr;

            while (i < len)
            {
                if (*expr == ')')
                {
                    if (--braces == 0)
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
                    braces++;
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
    txt = ''
    output = ''
    while i < lng-1:
        if e[i] == '$' and e[i+1] == '(':
            if txt != '':
                output += textCallb(moreArgs, txt)
            txt = ''
            code = ''
            i += 2
            braces = 1
            while i < lng:
                if e[i] == ')':
                    braces -= 1
                    if braces == 0:
                        output += varCallb(moreArgs,
                                           code, use_options, target, add_dict)
                        break
                    else:
                        code += e[i]
                elif e[i] == '(':
                    braces += 1
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
    output += textCallb(moreArgs, txt + e[i:])
    return output

*/
