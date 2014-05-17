#
#  This file is part of Bakefile (http://bakefile.org)
#
#  Copyright (C) 2003-2013 Vaclav Slavik
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy
#  of this software and associated documentation files (the "Software"), to
#  deal in the Software without restriction, including without limitation the
#  rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
#  sell copies of the Software, and to permit persons to whom the Software is
#  furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in
#  all copies or substantial portions of the Software.
#
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
#  FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
#  IN THE SOFTWARE.
#

"""
Misc. helpers for other Bakefile code.
"""

import copy
import functools
import collections


class OrderedDict(dict):
    """
    This is specialization of dictionary that preserves order of insertion
    when enumerating keys or items.
    """
    # TODO-PY26: replace this class with collections.OrderedDict() from Python 2.7/3.1

    # These must be overriden in derived class:
    def __init__(self, data=None):
        dict.__init__(self)
        self.order = []
        if data:
            self.update(data)

    def __setitem__(self, key, value):
        if not self.has_key(key):
            self.order.append(key)
        dict.__setitem__(self, key, value)
    def __delitem__(self, key):
        self.order.remove(key)
        dict.__delitem__(self, key)

    def __iter__(self):
        return iter(self.order)

    def __deepcopy__(self, memo):
        c = OrderedDict()
        for k,v in self.iteritems():
            c[k] = copy.deepcopy(v, memo)
        return c

    def __copy__(self):
        c = OrderedDict()
        c.update(self.iteritems())
        c.order = self.order[:]
        return c

    copy = __copy__

    # The rest is implemented using above methods:
    def update(self, other):
        if isinstance(other, dict):
            for k, v in other.iteritems():
                self[k] = v
        else:
            for k, v in other:
                self[k] = v

    def iterkeys(self):
        return self.__iter__()
    def iteritems(self):
        for k in self.iterkeys():
           yield (k, self[k])
    def itervalues(self):
        for k in self.iterkeys():
           yield self[k]

    def keys(self):
        return list(self.iterkeys())
    def items(self):
        return list(self.iteritems())
    def values(self):
        return list(self.itervalues())

    def __reduce__(self):
        "Return state information for pickling"
        return self.__class__, (self.items(),), {"order": self.order}


class OrderedSet(collections.MutableSet):
    """
    Set class that preserves insertion order during iteration.
    """
    def __init__(self, data=None):
        self._list = list()
        self._set = set()
        if data:
            self.update(data)

    def __contains__(self, x):
        return x in self._set

    def __len__(self):
        return len(self._list)

    def __iter__(self):
        return iter(self._list)

    def add(self, x):
        if x not in self._set:
            self._set.add(x)
            self._list.append(x)

    def discard(self, x):
        self._set.remove(x)
        self._list.remove(x)

    def update(self, other):
        for i in other:
            self.add(i)


def filter_duplicates(it):
    """
    Yields items from 'it', removing any duplicates.
    """
    found = set()
    for x in it:
        if x not in found:
            found.add(x)
            yield x


class memoized(object):
    """
    Decorator that caches a function's return value each time it is called.  If
    called later with the same arguments, the cached value is returned, and not
    re-evaluated.

    See http://wiki.python.org/moin/PythonDecoratorLibrary#Memoize
    """
    def __init__(self, func):
        self.func = func
        self.cache = {}

    def __call__(self, *args):
        try:
            return self.cache[args]
        except KeyError:
            value = self.func(*args)
            self.cache[args] = value
            return value
        except TypeError:
            # uncachable -- for instance, passing a list as an argument.
            # Better to not cache than to blow up entirely.
            return self.func(*args)

    def __repr__(self):
        """Return the function's docstring."""
        return self.func.__doc__

    def __get__(self, obj, objtype):
        """Support instance methods."""
        return functools.partial(self.__call__, obj)


class memoized_property(object):
    """
    Decorator for lazily evaluated properties.

    Use as the `@property` decorator. The method will only be called once,
    though. Subsequent uses of the property will use the previously returned
    value.
    """
    def __init__(self, func):
        self.func = func

    def __get__(self, obj, ownerClass=None):
        x = self.func(obj)
        setattr(obj, self.func.__name__, x)
        return x
