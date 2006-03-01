#
#  This file is part of Bakefile (http://bakefile.sourceforge.net)
#
#  Copyright (C) 2003,2004 Vaclav Slavik
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License version 2 as
#  published by the Free Software Foundation.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
#  $Id$
#
#  Misc container classes used by various parts of Bakefile
#

from __future__ import generators
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
