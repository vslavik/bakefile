
import xmlparser

_readerContext = []

def pushCtx(desc):
    if isinstance(desc, xmlparser.Element):
        _readerContext.append('at %s' % desc.location())
    else:
        _readerContext.append(desc)

def popCtx():
    _readerContext.pop()

class ErrorBase(Exception):
    def __init__(self, desc):
        self.desc = desc
    def __str__(self):
        s = ''
        for ctx in range(len(_readerContext)-1,-1,-1):
            s += "    %s\n" % _readerContext[ctx]
        return s

class Error(ErrorBase):
    def __init__(self, desc):
        ErrorBase.__init__(self, desc)
    def __str__(self):
        return 'error: %s\n%s' % (self.desc, ErrorBase.__str__(self))

class ReaderError(ErrorBase):
    def __init__(self, el, desc):
        ErrorBase.__init__(self, desc)
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
