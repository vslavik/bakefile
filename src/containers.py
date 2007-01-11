#
#  This file is part of Bakefile (http://bakefile.sourceforge.net)
#
#  Copyright (C) 2003-2007 Vaclav Slavik
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
#  $Id$
#
#  Misc container classes used by various parts of Bakefile
#

from __future__ import generators
import sys
import copy

class OrderedDict(dict):
    """This is specialization of dictionary that preserves order of insertion
       when enumerating keys or items."""

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
            c[k] = copy.deepcopy(self[k])
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


class OrderedDictWithClasification(OrderedDict):
    """Like OrderedDict, but items are categorized into several groups and 
       order is preserved only within the group. Groups are identified by their
       number (starting from 0) and are sorted by increasing group number.
       For example, this sequence of insertions:
          d[3] = ObjInGroup0
          d[2] = ObjInGroup1
          d[1] = ObjInGroup1
          d[8] = ObjInGroup0
       will result in this list returned by d.keys():
          [3,8,2,1]
    """

    def __init__(self, numGroups, getGroupPredicate):
        """numGroups is number of groups the values are classified into
           and getGroupPredicate is function that takes the value (not key!)
           as argument and returns group number."""
        OrderedDict.__init__(self)
        self.order = [ [] for i in range(0, numGroups) ]
        self.getGroup = getGroupPredicate
    
    def __setitem__(self, key, value):
        if not self.has_key(key):
            self.order[self.getGroup(value)].append(key)
        dict.__setitem__(self, key, value)
    def __delitem__(self, key):
        for group in self.order:
            if key in group:
                group.remove(key)
                return
        dict.__delitem__(self, key)
    
    def __iter__(self):
        for group in self.order:
            for k in group:
               yield k
    
    def __deepcopy__(self, memo):
        c = OrderedDictWithClasification(len(self.order), self.getGroup)
        for k in self.iterkeys():
            c[k] = copy.deepcopy(self[k])
        return c

if sys.version_info >= (2,4):

    class MergedDict:
        """This class implements "merged dictionary" - fake dictionary that
           serves as a proxy to ordered list of "slave" dictionaries. Lookups
           are performed by trying the slaves in order. Insertions and removals
           are done using temporary dict object that is initially empty."""
        def __init__(self):
            self.localdict = {}
            self.dicts = []

        def add(self, dict):
            """Adds a dictionary to the front of the list (i.e. variables in
               the latest added dictionary take precendence over variables
               from the lists added earlier)."""
            self.dicts.insert(0, dict)

        def dictForEval(self):
            """Returns dictionary that can be passed to eval()."""
            return self

        def __getitem__(self, key):
            if key in self.localdict:
                return self.localdict[key]
            for d in self.dicts:
                if key in d: return d[key]
            raise KeyError(key)

        def __contains__(self, key):
            for d in self.dicts:
                if key in d: return True
            return key in self.localdict
        
        def __setitem__(self, key, value):
            self.localdict.__setitem__(key, value)
        
        def __delitem__(self, key):
            self.localdict.__delitem__(key)

else:

    # MergedDict implementation for Python <= 2.3, which depends on an ugly
    # hack from bottlenecks.c:
    import bottlenecks

    class MergedDict:
        def __init__(self):
            self.proxy = bottlenecks.ProxyDictionary()
            self.dicts = []

        def add(self, dict):
            self.proxy.add(dict)
            self.dicts.insert(0, dict)
        
        def dictForEval(self):
            return self.proxy.dict

        def __contains__(self, key):
            for d in self.dicts:
                if key in d: return True
            return False
