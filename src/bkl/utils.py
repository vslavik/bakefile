#
#  This file is part of Bakefile (http://www.bakefile.org)
#
#  Copyright (C) 2003-2009 Vaclav Slavik
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

class OrderedDict(dict):
    """
    This is specialization of dictionary that preserves order of insertion
    when enumerating keys or items.
    """
    # FIXME: replace this class with collections.OrderedDict() from
    #        Python 2.7/3.1

    # These must be overriden in derived class:

    def __init__(self):
        dict.__init__(self)
        self.order = []

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
        for k in self.iterkeys():
            c[k] = copy.deepcopy(self[k], memo)
        return c

    # The rest is implemented using above methods:

    def update(self, dict):
        assert 0 # not permitted!
    def __copy__(self):
        assert 0 # not permitted!

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
