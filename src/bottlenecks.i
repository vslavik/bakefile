/*
 *  Assorted routines that were too slow when implemented in Python are
 *  implemented in C here for better performance.
 *
 *  $Id$
 *
 */


%module bottlenecks

%exception {
    $action
    if (result == NULL)
        return NULL;
}

/** Tokenizes input string \a expr that may contain Python expressions
    inside $(...) and calls \a textCallb(\a moreArgs, text)
    for text parts (outside $(...)) and
    \a varCallb(\a moreArgs, code, \a use_options, \a target, \a add_dict)
    for content of $(...). 
 */
extern const char *doEvalExpr(const char *expr,
                              PyObject *varCallb,
                              PyObject *textCallb,
                              PyObject *moreArgs,
                              PyObject *use_options,
                              PyObject *target,
                              PyObject *add_dict);
