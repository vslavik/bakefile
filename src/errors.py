#
#  This file is part of Bakefile (http://www.bakefile.org)
#
#  Copyright (C) 2003,2004 Vaclav Slavik
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
#  Exceptions classes and errors handling code
#

import copy
import xmlparser

_readerContext = []

def pushCtx(desc):
    if isinstance(desc, xmlparser.Element):
        _readerContext.append('at %s' % desc.location())
    else:
        _readerContext.append(desc)

def popCtx():
    _readerContext.pop()

def getCtx():
    return copy.deepcopy(_readerContext)

class ErrorBase(Exception):
    def __init__(self, desc, context=None):
        if context == None: context = _readerContext
        self.desc = desc
        self.context = copy.deepcopy(context)
    def getErrorMessage(self):
        return self.desc
    def __str__(self):
        s = ''
        for ctx in range(len(self.context)-1,-1,-1):
            s += "    %s\n" % self.context[ctx]
        return s

class Error(ErrorBase):
    def __init__(self, desc, context=None):
        ErrorBase.__init__(self, desc, context)
    def __str__(self):
        return 'error: %s\n%s' % (self.desc, ErrorBase.__str__(self))

class ReaderError(ErrorBase):
    def __init__(self, el, desc, context=None):
        ErrorBase.__init__(self, desc, context)
        self.element = el
    def __str__(self):
        s = ''
        if self.element != None:
            loc = self.element.location()
            s += "%s: error: %s\n" % (loc, self.desc)
        else:
            s += "error: %s\n" % self.desc
        s += ErrorBase.__str__(self)
        return s
