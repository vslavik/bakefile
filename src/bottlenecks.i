/*
 *  This file is part of Bakefile (http://bakefile.sourceforge.net)
 *
 *  Copyright (C) 2003-2006 Vaclav Slavik
 *
 *  This program is free software; you can redistribute it and/or modify
 *  it under the terms of the GNU General Public License version 2 as
 *  published by the Free Software Foundation.
 *
 *  This program is distributed in the hope that it will be useful,
 *  but WITHOUT ANY WARRANTY; without even the implied warranty of
 *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *  GNU General Public License for more details.
 *
 *  You should have received a copy of the GNU General Public License
 *  along with this program; if not, write to the Free Software
 *  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
 *
 *  $Id$
 *  
 *  Assorted routines that were too slow when implemented in Python are
 *  implemented in C here for better performance.
 *
 */


%module bottlenecks


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
