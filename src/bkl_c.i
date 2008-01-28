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


%module bkl_c


/* ------------------------------------------------------------------------ */
/*                          Expressions evaluation                          */
/* ------------------------------------------------------------------------ */

%exception doEvalExpr {
    $action
    if (result == NULL)
        return NULL;
}

/* Tokenizes input string \a expr that may contain Python expressions
   inside $(...) and calls \a textCallb(\a moreArgs, text)
   for text parts (outside $(...)) and
   \a varCallb(\a moreArgs, code, \a use_options, \a target, \a add_dict)
   for content of $(...). */
extern const char *doEvalExpr(const char *expr,
                              PyObject *varCallb,
                              PyObject *textCallb,
                              PyObject *moreArgs,
                              PyObject *use_options,
                              PyObject *target,
                              PyObject *add_dict);


/* ------------------------------------------------------------------------ */
/*           Fast merged dictionaries support for Python < 2.4              */
/* ------------------------------------------------------------------------ */

/* These functions and ProxyDictionary class are used to optimize 
   mk.__evalPyExpr function. It needs to pass a PyDict object to eval()
   function so that expression originating from $(...) can be evaluated
   in context of variables defined in bakefiles. Several variables
   dictionaries are used in the evaluation (target-specific one, additional
   variables, global variables and options), though. Original pure Python
   code merged the dicts into single dictionary that was then passed to
   eval():

       v = vlist[0].copy()
       for i in vlist[1:]: v.update(i)

   This was too slow (the dicts are _huge_ and __evalPyExpr is called very
   often; moreover, only small subset of the dicts is really used during the
   evaluation) and so bottlenecks.ProxyDictionary was born. This one takes
   lazy approach, it is something like "update on demand", except that no
   update is done. There's a dummy PyDict object that was hijacked using
   a Really Ugly Hack to route all PyDict_GetItem queries to other dictionaries
   (in order they were specified). This can't be done using clean code because
   the Python interpreter has hard-wired assumption that the dictionary passed
   to eval() wasn't subclassed in Python.

   As of Python 2.4, this hack is no longer needed because it's possible to
   use dict-like objects as eval's third argument. */

/* create proxy dictionary helper object: */
extern PyObject *proxydict_create(void);
/* hijack existing dictionary to route all requests through \a data: */
extern void proxydict_hijack(PyObject *data, PyObject *dict);
/* add new dictionary to the proxy: */
extern void proxydict_add(PyObject *data, PyObject *dict);

%pythoncode %{
class ProxyDictionary:
    def __init__(self):
        self.dict = {}
        self._catchall = {}
        self.data = proxydict_create()
        proxydict_hijack(self.data, self.dict)
        self.add(self._catchall)
    def add(self, d):
        proxydict_add(self.data, d)
%}
