#!/usr/bin/env python
#
# $Id$ $Date$

"""
A system for processing Python as markup embedded in text.
"""

__program__ = 'empy'
__version__ = '2.2'
__url__ = 'http://www.alcyone.com/pyos/empy/'
__author__ = 'Erik Max Francis <max@alcyone.com>'
__copyright__ = 'Copyright (C) 2002 Erik Max Francis'
__license__ = 'GPL'


import getopt
import os
import re
import string
import sys
import types

try:
    # equivalent of import cStringIO as StringIO
    import cStringIO
    StringIO = cStringIO
    del cStringIO
except ImportError:
    import StringIO

# For backward compatibility, we can't assume these are defined.
False, True = 0, 1

# Some basic defaults.
FAILURE_CODE = 1
DEFAULT_PREFIX = '@'
INTERNAL_MODULE_NAME = 'empy'
SIGNIFICATOR_RE_STRING = DEFAULT_PREFIX + r"%(\S)+\s*(.*)$"
BANGPATH = '#!'

# Environment variable names.
PREFIX_ENV = 'EMPY_PREFIX'
FLATTEN_ENV = 'EMPY_FLATTEN'
RAW_ENV = 'EMPY_RAW_ERRORS'
INTERACTIVE_ENV = 'EMPY_INTERACTIVE'
BUFFERED_ENV = 'EMPY_BUFFERED_OUTPUT'


class EmpyError(Exception):
    """The base class for all empy errors."""
    pass

class DiversionError(EmpyError):
    """An error related to diversions."""
    pass

class FilterError(EmpyError):
    """An error related to filters."""
    pass

class StackUnderflowError(EmpyError):
    """A stack underflow."""
    pass

class CommandLineError(EmpyError):
    """An error triggered by errors in the command line."""
    pass

class HookError(EmpyError):
    """An error associated with hooks."""
    pass

class ParseError(EmpyError):
    """A parse error occurred."""
    pass

class TransientParseError(ParseError):
    """A parse error occurred which may be resolved by feeding more data.
    Such an error reaching the toplevel is an unexpected EOF error."""
    pass


class MetaError(Exception):

    """A wrapper around a real Python exception for including a copy of
    the context."""
    
    def __init__(self, contexts, exc):
        Exception.__init__(self, exc)
        self.contexts = contexts
        self.exc = exc

    def __str__(self):
        backtrace = map(lambda x: "%s:%s" % (x.name, x.line), self.contexts)
        return "%s: %s (%s)" % (self.exc.__class__, self.exc, \
                                (string.join(backtrace, ', ')))


class Stack:
    
    """A simple stack that behaves as a sequence (with 0 being the top
    of the stack, not the bottom)."""

    def __init__(self, seq=None):
        if seq is None:
            seq = []
        self.data = seq

    def top(self):
        """Access the top element on the stack."""
        try:
            return self.data[-1]
        except IndexError:
            raise StackUnderflowError, "stack is empty for top"
        
    def pop(self):
        """Pop the top element off the stack and return it."""
        try:
            return self.data.pop()
        except IndexError:
            raise StackUnderflowError, "stack is empty for pop"
        
    def push(self, object):
        """Push an element onto the top of the stack."""
        self.data.append(object)

    def purge(self):
        """Purge the stack."""
        self.data = []

    def clone(self):
        """Create a duplicate of this stack."""
        return self.__class__(self.data[:])

    def __nonzero__(self): return len(self.data) != 0
    def __len__(self): return len(self.data)
    def __getitem__(self, index): return self.data[-(index + 1)]


class AbstractFile:
    
    """An abstracted file that, when buffered, will totally buffer the
    file, including even the file open."""

    def __init__(self, filename, mode='w', bufferedOutput=False):
        self.filename = filename
        self.mode = mode
        self.bufferedOutput = bufferedOutput
        if bufferedOutput:
            self.bufferFile = StringIO.StringIO()
        else:
            self.bufferFile = open(filename, mode)
        self.done = False

    def __del__(self):
        self.close()

    def write(self, data):
        self.bufferFile.write(data)

    def writelines(self, data):
        self.bufferFile.writelines(data)

    def flush(self):
        self.bufferFile.flush()

    def close(self):
        if not self.done:
            self.commit()
            self.done = True

    def commit(self):
        if self.bufferedOutput:
            file = open(self.filename, self.mode)
            file.write(self.bufferFile.getvalue())
            file.close()
        else:
            self.bufferFile.close()

    def abort(self):
        if self.bufferedOutput:
            self.bufferFile = None
        else:
            self.bufferFile.close()
            self.bufferFile = None
        self.done = True


class Diversion:

    """The representation of an active diversion.  Diversions act as
    (writable) file objects, and then can be recalled either as pure
    strings or (readable) file objects."""

    def __init__(self):
        self.file = StringIO.StringIO()

    # These methods define the writable file-like interface for the
    # diversion.

    def write(self, data):
        self.file.write(data)

    def writelines(self, lines):
        for line in lines:
            self.write(line)

    def flush(self):
        self.file.flush()

    def close(self):
        self.file.close()

    def asString(self):
        """Return the diversion as a string."""
        return self.file.getvalue()

    def asFile(self):
        """Return the diversion as a file."""
        return StringIO.StringIO(self.file.getvalue())


class Stream:
    
    """A wrapper around an (output) file object which supports
    diversions and filtering."""
    
    def __init__(self, file):
        self.file = file
        self.currentDiversion = None
        self.diversions = {}
        self.filter = file
        self.done = False

    def write(self, data):
        if self.currentDiversion is None:
            self.filter.write(data)
        else:
            self.diversions[self.currentDiversion].write(data)
    
    def writelines(self, lines):
        for line in lines:
            self.write(line)

    def flush(self):
        self.filter.flush()

    def close(self):
        if not self.done:
            self.undivertAll(True)
            self.filter.close()
            self.done = True

    def install(self, filter=None):
        """Install a new filter; None means no filter.  Handle all the
        special shortcuts for filters here."""
        # Before starting, execute a flush.
        self.filter.flush()
        if filter is None or filter == [] or filter == ():
            # Shortcuts for "no filter."
            self.filter = self.file
        else:
            if type(filter) in (types.ListType, types.TupleType):
                filterShortcuts = list(filter)
            else:
                filterShortcuts = [filter]
            filters = []
            # Run through the shortcut filter names, replacing them with
            # full-fledged instances of Filter.
            for filter in filterShortcuts:
                if filter == 0:
                    filters.append(NullFilter())
                elif type(filter) is types.FunctionType or \
                     type(filter) is types.BuiltinFunctionType or \
                     type(filter) is types.BuiltinMethodType or \
                     type(filter) is types.LambdaType:
                    filters.append(FunctionFilter(filter))
                elif type(filter) is types.StringType:
                    filters.append(StringFilter(filter))
                elif type(filter) is types.DictType:
                    raise NotImplementedError, \
                          "mapping filters not yet supported"
                else:
                    filters.append(filter) # assume it's a Filter
            if len(filters) > 1:
                # If there's more than one filter provided, chain them
                # together.
                lastFilter = None
                for filter in filters:
                    if lastFilter is not None:
                        lastFilter.attach(filter)
                    lastFilter = filter
                lastFilter.attach(self.file)
                self.filter = filters[0]
            else:
                # If there's only one filter, assume that it's alone or it's
                # part of a chain that has already been manually chained;
                # just find the end.
                filter = filters[0]
                thisFilter, lastFilter = filter, filter
                while thisFilter is not None:
                    lastFilter = thisFilter
                    thisFilter = thisFilter.sink
                lastFilter.attach(self.file)
                self.filter = filter

    def revert(self):
        """Reset any current diversions."""
        self.currentDiversion = None

    def create(self, name):
        """Create a diversion if one does not already exist, but do not
        divert to it yet."""
        if name is None:
            raise DiversionError, "diversion name must be non-None"
        if not self.diversions.has_key(name):
            self.diversions[name] = Diversion()

    def retrieve(self, name):
        """Retrieve the given diversion."""
        if name is None:
            raise DiversionError, "diversion name must be non-None"
        if self.diversions.has_key(name):
            return self.diversions[name]
        else:
            raise DiversionError, "nonexistent diversion: %s" % name

    def divert(self, name):
        """Start diverting."""
        if name is None:
            raise DiversionError, "diversion name must be non-None"
        self.create(name)
        self.currentDiversion = name

    def undivert(self, name, purgeAfterwards=False):
        """Undivert a particular diversion."""
        if name is None:
            raise DiversionError, "diversion name must be non-None"
        if self.diversions.has_key(name):
            diversion = self.diversions[name]
            self.filter.write(diversion.asString())
            if purgeAfterwards:
                self.purge(name)
        else:
            raise DiversionError, "nonexistent diversion: %s" % name

    def purge(self, name):
        """Purge the specified diversion."""
        if name is None:
            raise DiversionError, "diversion name must be non-None"
        if self.diversions.has_key(name):
            del self.diversions[name]
            if self.currentDiversion == name:
                self.currentDiversion = None

    def undivertAll(self, purgeAfterwards=True):
        """Undivert all pending diversions."""
        if self.diversions:
            self.revert() # revert before undiverting!
            names = self.diversions.keys()
            names.sort()
            for name in names:
                self.undivert(name)
                if purgeAfterwards:
                    self.purge(name)
            
    def purgeAll(self):
        """Eliminate all existing diversions."""
        if self.diversions:
            self.diversions = {}
        self.currentDiversion = None


class ProxyFile:

    """The proxy file object that is intended to take the place of
    sys.stdout.  The proxy can manage a stack of file objects it is
    writing to, and an underlying raw file object."""

    def __init__(self, rawFile):
        self.stack = Stack()
        self.raw = rawFile
        self.current = rawFile

    def push(self, file):
        self.stack.push(file)
        self.current = file

    def pop(self):
        result = self.stack.pop()
        if self.stack:
            self.current = self.stack[-1]
        else:
            self.current = self.raw
        return result

    def purge(self):
        self.stack.purge()

    def write(self, data):
        self.current.write(data)

    def writelines(self, lines):
        self.current.writelines(lines)

    def flush(self):
        self.current.flush()

    def close(self):
        if self.current is not None:
            self.current.close()
            self.current = None


class Filter:

    """An abstract filter."""

    def __init__(self):
        if self.__class__ is Filter:
            raise NotImplementedError
        self.sink = None

    def write(self, data):
        raise NotImplementedError

    def writelines(self, lines):
        for line in lines:
            self.write(line)

    def _flush(self):
        """The _flush method should always flush and should not be
        overridden."""
        self.sink.flush()

    def flush(self):
        """The flush method can be overridden."""
        self._flush()

    def close(self):
        self.flush()
        self.sink.close()

    def attach(self, filter):
        """Attach a filter to this one."""
        self.sink = filter

    def last(self):
        """Find the last filter in this chain."""
        this, last = self, self
        while this is not None:
            last = this
            this = this.sink
        return last

class NullFilter(Filter):

    """A filter that never sends any output to its sink."""

    def write(self, data): pass

class FunctionFilter(Filter):

    """A filter that works simply by pumping its input through a
    function which maps strings into strings."""
    
    def __init__(self, function):
        Filter.__init__(self)
        self.function = function

    def write(self, data):
        self.sink.write(self.function(data))

class StringFilter(Filter):

    """A filter that takes a translation string (256 characters) and
    filters any incoming data through it."""

    def __init__(self, table):
        if not (type(table) == types.StringType and len(table) == 256):
            raise FilterError, "table must be 256-character string"
        Filter.__init__(self)
        self.table = table

    def write(self, data):
        self.sink.write(string.translate(data, self.table))

class BufferedFilter(Filter):

    """A buffered filter is one that doesn't modify the source data
    sent to the sink, but instead holds it for a time.  The standard
    variety only sends the data along when it receives a flush
    command."""

    def __init__(self):
        Filter.__init__(self)
        self.buffer = ''

    def write(self, data):
        self.buffer = self.buffer + data

    def flush(self):
        if self.buffer:
            self.sink.write(self.buffer)
        self.sink.flush()

class SizeBufferedFilter(BufferedFilter):

    """A size-buffered filter only in fixed size chunks (excepting the
    final chunk)."""

    def __init__(self, bufferSize):
        BufferedFilter.__init__(self)
        self.bufferSize = bufferSize

    def write(self, data):
        BufferedFilter.write(self, data)
        while len(self.buffer) > self.bufferSize:
            chunk, self.buffer = \
                self.buffer[:self.bufferSize], self.buffer[self.bufferSize:]
            self.sink.write(chunk)

class LineBufferedFilter(BufferedFilter):

    """A line-buffered filter only lets data through when it sees
    whole lines."""

    def __init__(self):
        BufferedFilter.__init__(self)

    def write(self, data):
        BufferedFilter.write(self, data)
        chunks = string.split(self.buffer, '\n')
        for chunk in chunks[:-1]:
            self.sink.write(chunk + '\n')
        self.buffer = chunks[-1]

class MaximallyBufferedFilter(BufferedFilter):

    """A maximally-buffered filter only lets its data through on the final
    close.  It ignores flushes."""

    def __init__(self):
        BufferedFilter.__init__(self)

    def flush(self): pass

    def close(self):
        if self.buffer:
            BufferedFilter.flush(self)
            self.sink.close()


class Scanner:

    """A scanner holds a buffer for lookahead parsing and has the
    ability to scan for special tokens and indicators in that
    buffer."""
    
    def __init__(self, data=None):
        self.buffer = ''
        if data is not None:
            self.set(data)

    def __nonzero__(self): return self.buffer
    def __len__(self): return len(self.buffer)
    def __getitem__(self, index): return self.buffer[index]

    def set(self, data):
        """Start the scanner digesting a new batch of data; start the pointer
        over from scratch."""
        self.buffer = data

    def feed(self, data):
        """Feed some more data to the scanner."""
        self.buffer = self.buffer + data

    def push(self, data):
        """Push data back; the reverse of chop."""
        self.buffer = data + self.buffer

    def rest(self):
        """Get the remainder of the buffer."""
        return self.buffer

    def chop(self, count=None, slop=False):
        """Chop the first count + slop characters off the front, and return
        the first count.  If count is not specified, then return
        everything."""
        if count is None:
            count = len(self.buffer)
        result, self.buffer = self.buffer[:count], self.buffer[count + slop:]
        return result

    def read(self, i=0, count=1):
        """Read count chars starting from i; raise a transient error if
        there aren't enough characters remaining."""
        if len(self.buffer) < i + count:
            raise TransientParseError, "need more data to read"
        else:
            return self.buffer[i:i + count]

    def check(self, i, archetype=None):
        """Scan for the next single or triple quote, with the specified
        archetype (if the archetype is present, only trigger on those types
        of quotes.  Return the found quote or None."""
        quote = None
        if self.buffer[i] in '\'\"':
            quote = self.buffer[i]
            if len(self.buffer) - i < 3:
                for j in range(i, len(self.buffer)):
                    if self.buffer[i] == quote:
                        return quote
                else:
                    raise TransientParseError, "need to scan for rest of quote"
            if self.buffer[i + 1] == self.buffer[i + 2] == quote:
                quote = quote * 3
        if quote is not None:
            if archetype is None:
                return quote
            else:
                if archetype == quote:
                    return quote
                elif len(archetype) < len(quote) and archetype[0] == quote[0]:
                    return archetype
                else:
                    return None
        else:
            return None

    def find(self, sub, start=0, end=None):
        """Find the next occurrence of the character, or return -1."""
        if end is not None:
            return string.find(self.buffer, sub, start, end)
        else:
            return string.find(self.buffer, sub, start)

    def next(self, target, start=0, end=None, mandatory=False):
        """Scan from i to j for the next occurrence of one of the characters
        in the target string; optionally, make the scan mandatory."""
        if mandatory:
            assert end is not None
        quote = None
        if end is None:
            end = len(self.buffer)
        i = start
        while i < end:
            newQuote = self.check(i, quote)
            if newQuote:
                if newQuote == quote:
                    quote = None
                else:
                    quote = newQuote
                i = i + len(newQuote)
            else:
                c = self.buffer[i]
                if quote:
                    if c == '\\':
                        i = i + 1
                else:
                    if c in target:
                        return i
                i = i + 1
        else:
            if mandatory:
                raise ParseError, "expecting %s, not found" % target
            else:
                raise TransientParseError, "expecting ending character"

    def complex(self, enter, exit, start=0, end=None, skip=None):
        """Scan from i for an ending sequence, respecting entries and
        exits."""
        quote = None
        depth = 0
        if end is None:
            end = len(self.buffer)
        last = None
        i = start
        while i < end:
            newQuote = self.check(i, quote)
            if newQuote:
                if newQuote == quote:
                    quote = None
                else:
                    quote = newQuote
                i = i + len(newQuote)
            else:
                c = self.buffer[i]
                if quote:
                    if c == '\\':
                        i = i + 1
                else:
                    if skip is None or last != skip:
                        if c == enter:
                            depth = depth + 1
                        elif c == exit:
                            depth = depth - 1
                            if depth < 0:
                                return i
                last = c
                i = i + 1
        else:
            raise TransientParseError, "expecting end of complex expression"

    def word(self, start=0):
        """Scan from i for a simple word."""
        self.bufferLen = len(self.buffer)
        i = start
        while i < self.bufferLen:
            if not self.buffer[i] in Interpreter.IDENTIFIER_REST:
                return i
            i = i + 1
        else:
            raise TransientParseError, "expecting end of word"

    def phrase(self, start=0):
        """Scan from i for a phrase (e.g., 'word', 'f(a, b, c)', 'a[i]', or
        combinations like 'x[i](a)'."""
        # Find the word.
        i = self.word(start)
        while i < len(self.buffer) and self.buffer[i] in '([':
            enter = self.buffer[i]
            exit = Interpreter.ENDING_CHARS[enter]
            i = self.complex(enter, exit, i + 1) + 1
        return i
    
    def simple(self, start=0):
        """Scan from i for a simple expression, which consists of one 
        more phrases separated by dots."""
        i = self.phrase(start)
        self.bufferLen = len(self.buffer)
        while i < self.bufferLen and self.buffer[i] == '.':
            i = self.phrase(i)
        # Make sure we don't end with a trailing dot.
        while i > 0 and self.buffer[i - 1] == '.':
            i = i - 1
        return i

    def keyword(self, word, start=0, end=None, mandatory=False):
        prefix = word[0] # keywords start with a prefix
        if mandatory:
            assert end is not None
        i = -1
        while 1:
            i = string.find(self.buffer, word, i + 1, end)
            if i < 0:
                if mandatory:
                    raise ParseError, "missing keyword %s" % word
                else:
                    raise TransientParseError, "missing keyword %s" % word
            if i == 0 or (i > 0 and self.buffer[i - 1] != prefix):
                return i


class Context:
    
    """An interpreter context, which encapsulates a name, an input
    file object, and a parser object."""

    def __init__(self, name, line=0):
        self.name = name
        self.line = line

    def bump(self):
        self.line = self.line + 1

    def identify(self):
        return self.name, self.line


class PseudoModule:
    
    """A pseudomodule for the builtin empy routines."""

    __name__ = INTERNAL_MODULE_NAME

    # Constants.

    VERSION = __version__
    SIGNIFICATOR_RE_STRING = SIGNIFICATOR_RE_STRING

    # Types.

    Filter = Filter
    NullFilter = NullFilter
    FunctionFilter = FunctionFilter
    StringFilter = StringFilter
    BufferedFilter = BufferedFilter
    SizeBufferedFilter = SizeBufferedFilter
    LineBufferedFilter = LineBufferedFilter
    MaximallyBufferedFilter = MaximallyBufferedFilter

    def __init__(self, interpreter):
        self.interpreter = interpreter
        self.argv = interpreter.argv
        self.args = interpreter.argv[1:]

    # Identification.

    def identify(self):
        """Identify the topmost context with a 2-tuple of the name and
        line number."""
        return self.interpreter.context().identify()

    def setName(self, name):
        """Set the name of the topmost context."""
        context = self.interpreter.context()
        context.name = name
        
    def setLine(self, line):
        """Set the name of the topmost context."""
        context = self.interpreter.context()
        context.line = line

    def atExit(self, callable):
        """Register a function to be called at exit."""
        self.interpreter.finals.append(callable)

    # Hook support.

    def getHooks(self, name):
        """Get the hooks associated with the name."""
        try:
            return self.interpreter.hooks[name]
        except KeyError:
            return []

    def clearHooks(self, name):
        """Clear all hooks associated with the name."""
        if self.interpreter.hooks.has_key(name):
            del self.interpreter.hooks[name]

    def addHook(self, name, hook, prepend=False):
        """Add a new hook; optionally insert it rather than appending it."""
        if self.interpreter.hooks.has_key(name):
            if prepend:
                self.interpreter.hooks[name].insert(0, hook)
            else:
                self.interpreter.hooks[name].append(hook)
        else:
            self.interpreter.hooks[name] = [hook]

    def removeHook(self, name, hook):
        """Remove a particular hook."""
        try:
            self.interpreter.hooks[name].remove(hook)
        except (KeyError, ValueError):
            raise HookError, "could not remove hook: %s" % name

    def invokeHook(self, name_, **keywords):
        """Manually invoke a hook."""
        apply(self.interpreter.invoke, (name_,), keywords)

    # Source manipulation.

    def include(self, fileOrFilename, locals=None, processBangpaths=True):
        """Wrapper around include."""
        self.interpreter.include(fileOrFilename, locals, processBangpaths)

    def expand(self, data, locals=None):
        """Wrapper around expand."""
        return self.interpreter.expand(data, locals)

    def string(self, data, name='<string>', locals=None):
        """Wrapper around string."""
        self.interpreter.string(data, name, locals)

    def quote(self, data):
        """Wrapper around quote."""
        return self.interpreter.quote(data)

    def escape(self, data, more=''):
        """Wrapper around escape."""
        return self.interpreter.escape(data, more)

    def flush(self):
        """Wrapper around flush."""
        self.interpreter.flush()

    # Pseudomodule manipulation.

    def flatten(self, keys=None):
        """Flatten the contents of the pseudo-module into the globals
        namespace."""
        if keys is None:
            keys = self.__dict__.keys() + self.__class__.__dict__.keys()
        dict = {}
        for key in keys:
            # The pseudomodule is really a class instance, so we need to
            # fumble use getattr instead of simply fumbling through the
            # instance's __dict__.
            dict[key] = getattr(self, key)
        # Stomp everything into the globals namespace.
        self.interpreter.globals.update(dict)

    # Prefix.

    def getPrefix(self):
        """Get the current prefix."""
        return self.interpreter.prefix

    def setPrefix(self, prefix):
        """Set the prefix."""
        self.interpreter.prefix = prefix

    # Diversions.

    def stopDiverting(self):
        """Stop any diverting."""
        self.interpreter.stream().revert()

    def createDiversion(self, name):
        """Create a diversion (but do not divert to it) if it does not
        already exist."""
        self.interpreter.stream().create(name)

    def retrieveDiversion(self, name):
        """Retrieve the diversion object associated with the name."""
        return self.interpreter.stream().retrieve(name)

    def startDiversion(self, name):
        """Start diverting to the given diversion name."""
        self.interpreter.stream().divert(name)

    def playDiversion(self, name):
        """Play the given diversion and then purge it."""
        self.interpreter.stream().undivert(name, True)

    def replayDiversion(self, name):
        """Replay the diversion without purging it."""
        self.interpreter.stream().undivert(name, False)

    def purgeDiversion(self, name):
        """Eliminate the given diversion."""
        self.interpreter.stream().purge(name)

    def playAllDiversions(self):
        """Play all existing diversions and then purge them."""
        self.interpreter.stream().undivertAll(True)

    def replayAllDiversions(self):
        """Replay all existing diversions without purging them."""
        self.interpreter.stream().undivertAll(False)

    def purgeAllDiversions(self):
        """Purge all existing diversions."""
        self.interpreter.stream().purgeAll()

    def getCurrentDiversion(self):
        """Get the name of the current diversion."""
        return self.interpreter.stream().currentDiversion

    def getAllDiversions(self):
        """Get the names of all existing diversions."""
        names = self.interpreter.stream().diversions.keys()
        names.sort()
        return names
    
    # Filter.

    def resetFilter(self):
        """Reset the filter so that it does no filtering."""
        self.interpreter.stream().install(None)

    def nullFilter(self):
        """Install a filter that will consume all text."""
        self.interpreter.stream().install(0)

    def getFilter(self):
        """Get the current filter."""
        filter = self.interpreter.stream().filter
        if filter is self.interpreter.stream().file:
            return None
        else:
            return filter

    def setFilter(self, filter):
        """Set the filter."""
        self.interpreter.stream().install(filter)


class Interpreter:
    
    """An interpreter can process chunks of empy code."""

    SECONDARY_CHARS = "#%([{)]}`: \t\v\r\n\\"
    IDENTIFIER_FIRST = '_abcdefghijklmnopqrstuvwxyz' + \
                       'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    IDENTIFIER_REST = IDENTIFIER_FIRST + '0123456789.'
    ENDING_CHARS = {'(': ')', '[': ']', '{': '}'}
    ESCAPE_CODES = {0x00: '0', 0x07: 'a', 0x08: 'b', 0x1b: 'e', 0x0c: 'f', \
                    0x7f: 'h', 0x0a: 'n', 0x0d: 'r', 0x09: 't', 0x0b: 'v', \
                    0x04: 'z'}

    IF_RE = re.compile(r"^if\s+(.*)$")
    WHILE_RE = re.compile(r"^while\s+(.*)$")
    FOR_RE = re.compile(r"^for\s+(\S+)\s+in\s+(.*)$")
    MACRO_RE = re.compile(r"^macro\s+(.*)$")

    # Construction, destruction.

    def __init__(self, output=None, argv=None, globals=None, \
                 prefix=DEFAULT_PREFIX):
        # Set up the stream.
        if output is None:
            output = sys.__stdout__
        self.output = output
        self.prefix = prefix
        self.hooks = {}
        self.finals = []
        # The interpreter arguents.
        if argv is None:
            argv = []
        self.argv = argv
        # The interpreter stacks.
        self.contexts = Stack()
        self.streams = Stack()
        # Set up the globals; this should come after everything else since
        # the pseudmodule relies on the interpreter being prepared.
        self.pseudo = PseudoModule(self)
        if globals is None:
            globals = {}
        globals[self.pseudo.__name__] = self.pseudo
        self.globals = globals
        # Install a proxy stdout if one hasn't been already.
        self.installProxy()
        # Finally, reset the state of all the stacks.
        self.reset()

    def __del__(self):
        self.shutdown()

    def shutdown(self):
        """Declare this interpreting session over; close the stream file
        object."""
        if self.streams is not None:
            self.invoke('at_shutdown')
            self.finalize()
            while self.streams:
                stream = self.streams.pop()
                stream.close()
            self.streams = None

    # Writeable file-like methods.

    def write(self, data):
        self.stream().write(data)

    def writelines(self, stuff):
        self.stream().writelines(stuff)

    def flush(self):
        self.stream().flush()

    def close(self):
        self.shutdown()

    # Stack-related activity.

    def context(self):
        return self.contexts.top()

    def stream(self):
        return self.streams.top()

    def reset(self):
        self.contexts.purge()
        self.streams.purge()
        self.streams.push(Stream(self.output))
        sys.stdout.purge()

    # Higher-level operaitons.

    def include(self, fileOrFilename, locals=None, processBangpaths=True):
        """Do an include pass on a file or filename."""
        if type(fileOrFilename) is types.StringType:
            # Either it's a string representing a filename ...
            filename = fileOrFilename
            name = filename
            file = open(filename, 'r')
        else:
            # ... or a file object.
            file = fileOrFilename
            name = "<%s>" % str(file.__class__)
        self.invoke('before_include', name=name, file=file)
        self.file(file, name, locals, processBangpaths)
        self.invoke('after_include')

    def expand(self, data, locals=None):
        """Do an explicit expansion on a subordinate stream."""
        outFile = StringIO.StringIO()
        stream = Stream(outFile)
        self.invoke('before_expand', string=data, locals=locals)
        self.streams.push(stream)
        try:
            self.string(data, '<expand>', locals)
            stream.flush()
            expansion = outFile.getvalue()
            self.invoke('after_expand')
            return expansion
        finally:
            self.streams.pop()

    def quote(self, data):
        """Quote the given string so that if it were expanded it would
        evaluate to the original."""
        self.invoke('at_quote', string=data)
        scanner = Scanner(data)
        result = []
        i = 0
        try:
            j = scanner.next(self.prefix, i)
            result.append(data[i:j])
            result.append(self.prefix * 2)
            i = j + 1
        except TransientParseError:
            pass
        result.append(data[i:])
        return string.join(result, '')

    def escape(self, data, more=''):
        """Escape a string so that nonprintable characters are replaced
        with compatible empy expansions."""
        self.invoke('at_escape', string=data, more=more)
        result = []
        for char in data:
            if char < ' ' or char > '~':
                charOrd = ord(char)
                if Interpreter.ESCAPE_CODES.has_key(charOrd):
                    result.append(self.prefix + '\\' + \
                                  Interpreter.ESCAPE_CODES[charOrd])
                else:
                    result.append(self.prefix + '\\x%02x' % charOrd)
            elif char in more:
                result.append(self.prefix + '\\' + char)
            else:
                result.append(char)
        return string.join(result, '')

    # Processing.

    def wrap(self, callable, args, \
             bufferedOutput=False, rawErrors=False, exitOnError=True):
        """Wrap around an application of a callable and handle errors.
        Return true if no error occurs."""
        try:
            apply(callable, args)
            self.reset()
            return True
        except KeyboardInterrupt, e:
            # Handle keyboard interrupts specially: override the
            # exitOnError option and always exit from them.
            self.die(e, bufferedOutput, rawErrors, True)
        except Exception, e:
            # A standard exception (other than a keyboard interrupt).
            self.die(e, bufferedOutput, rawErrors, exitOnError)
        except:
            # If we get here, then it must be a string exception, 
            # so get the error info from the sys module.
            e = sys.exc_type
            self.die(e, bufferedOutput, rawErrors, exitOnError)
        # An error occurred if we get here.
        self.reset()
        return False

    def interact(self, \
                 bufferedOutput=False, rawErrors=False, exitOnError=True):
        """Perform interaction."""
        done = False
        while not done:
            result = self.wrap(self.file, (sys.stdin, '<interact>'), \
                               bufferedOutput, rawErrors, exitOnError)
            if exitOnError:
                done = True
            else:
                if result:
                    done = True
                else:
                    self.reset()

    def die(self, error, \
            bufferedOutput=False, rawErrors=False, exitOnError=True):
        """Handle an actual error that occurred."""
        if bufferedOutput:
            self.output.abort()
        meta = self.meta(error)
        self.handle(meta)
        if rawErrors:
            raise
        if exitOnError:
            sys.exit(FAILURE_CODE)

    def file(self, file, name='<file>', locals=None, processBangpaths=True):
        """Parse the entire contents of a file.  processBangpaths indicates
        whether or not a bangpath at the start of a file will be treated
        as a comment."""
        context = Context(name)
        self.contexts.push(context)
        self.invoke('before_file', name=name, file=file)
        scanner = Scanner()
        first = True
        done = False
        while not done:
            context.bump()
            line = file.readline()
            if first:
                if processBangpaths:
                    # Replace a bangpath at the beginning of the first line
                    # with an empy comment.
                    if string.find(line, BANGPATH) == 0:
                        line = self.prefix + '#' + line[2:]
                first = False
            if line:
                scanner.feed(line)
            else:
                done = True
            self.safe(scanner, done, locals)
        self.invoke('after_file')
        self.contexts.pop()

    def string(self, data, name='<string>', locals=None):
        """Parse a string."""
        context = Context(name)
        self.contexts.push(context)
        self.invoke('before_string', name=name, string=data)
        context.bump()
        scanner = Scanner(data)
        self.safe(scanner, True, locals)
        self.invoke('after_string')
        self.contexts.pop()

    def safe(self, scanner, final=False, locals=None):
        """Do a protected parse.  Catch transient parse errors; if
        final is true, then make a final pass with a terminator,
        otherwise ignore the transient parse error (more data is
        pending)."""
        try:
            self.parse(scanner, locals)
        except TransientParseError:
            if final:
                # If the buffer doesn't end with a newline, try tacking on
                # a dummy terminator.
                buffer = scanner.rest()
                if buffer and buffer[-1] != '\n':
                    scanner.feed(self.prefix + '\n')
                # A TransientParseError thrown from here is a real parse
                # error.
                self.parse(scanner, locals)

    def parse(self, scanner, locals=None):
        """Parse as much from this scanner as possible."""
        self.invoke('at_parse', scanner=scanner)
        while 1:
            loc = scanner.find(self.prefix)
            if loc < 0:
                # The prefix isn't in the buffer, which means we can just
                # flush it all.
                self.stream().write(scanner.chop())
                break
            else:
                # Flush the characters before the prefix.
                self.stream().write(scanner.chop(loc, 1))
                self.one(scanner, locals)

    def one(self, scanner, locals=None):
        """Process exactly one expansion (starting at the beginning of
        the buffer)."""
        primary = scanner.chop(1)
        try:
            if primary in ' \t\v\r\n':
                # Whitespace/line continuation.
                pass
            elif primary in ')]}':
                self.stream().write(primary)
            elif primary == '\\':
                try:
                    code = scanner.read(0)
                    i = 1
                    result = None
                    if code in '()[]{}\'\"\\': # literals
                        result = code
                    elif code == '0': # NUL
                        result = '\x00'
                    elif code == 'a': # BEL
                        result = '\x07'
                    elif code == 'b': # BS
                        result = '\x08'
                    elif code == 'd': # decimal code
                        decimalCode = scanner.read(i, 3)
                        i = i + 3
                        result = chr(string.atoi(decimalCode, 10))
                    elif code == 'e': # ESC
                        result = '\x1b'
                    elif code == 'f': # FF
                        result = '\x0c'
                    elif code == 'h': # DEL
                        result = '\x7f'
                    elif code == 'n': # LF (newline)
                        result = '\x0a'
                    elif code == 'o': # octal code
                        octalCode = scanner.read(i, 3)
                        i = i + 3
                        result = chr(string.atoi(octalCode, 8))
                    elif code == 'q': # quaternary coe
                        quaternaryCode = scanner.read(i, 4)
                        i = i + 4
                        result = chr(string.atoi(quaternaryCode, 4))
                    elif code == 'r': # CR
                        result = '\x0d'
                    elif code in 's ': # SP
                        result = ' '
                    elif code == 't': # HT
                        result = '\x09'
                    elif code == 'u': # unicode
                        raise NotImplementedError, "no Unicode support"
                    elif code == 'v': # VT
                        result = '\x0b'
                    elif code == 'x': # hexadecimal code
                        hexCode = scanner.read(i, 2)
                        i = i + 2
                        result = chr(string.atoi(hexCode, 16))
                    elif code == 'z': # EOT
                        result = '\x04'
                    elif code == '^': # control character
                        controlCode = string.upper(scanner.read(i))
                        i = i + 1
                        if controlCode >= '@' and controlCode <= '`':
                            result = chr(ord(controlCode) - ord('@'))
                        elif controlCode == '?':
                            result = '\x7f'
                        else:
                            raise ParseError, "invalid escape control code"
                    else:
                        raise ParseError, "unrecognized escape code"
                    assert result is not None
                    self.stream().write(result)
                    scanner.chop(i)
                except ValueError:
                    raise ParseError, "invalid numeric escape code"
            elif primary in Interpreter.IDENTIFIER_FIRST:
                # "Simple expression" expansion.
                i = scanner.simple()
                code = primary + scanner.chop(i)
                result = self.evaluate(code, locals)
                if result is not None:
                    self.stream().write(str(result))
            elif primary == '#':
                # Comment.
                loc = scanner.find('\n')
                if loc >= 0:
                    scanner.chop(loc, 1)
                else:
                    raise TransientParseError, "comment expects newline"
            elif primary == '%':
                # Significator.
                loc = scanner.find('\n')
                if loc >= 0:
                    line = scanner.chop(loc, 1)
                    if not line:
                        raise ParseError, "significator must have nonblank key"
                    if line[0] in ' \t\v\n':
                        raise ParseError, "no whitespace between % and key"
                    fields = string.split(line, None, 1)
                    if len(fields) < 2:
                        key = fields[0]
                        value = None
                    else:
                        key, rawValue = fields
                        rawValue = string.strip(rawValue)
                        value = self.evaluate(rawValue, locals)
                    self.significate(key, value)
                else:
                    raise TransientParseError, "significator expects newline"
            elif primary == '(':
                # Uber-expression evaluation.
                z = scanner.complex('(', ')', 0)
                try:
                    q = scanner.next('$', 0, z, True)
                except ParseError:
                    q = z
                try:
                    i = scanner.next('?', 0, q, True)
                    try:
                        j = scanner.next(':', i, q, True)
                    except ParseError:
                        j = q
                except ParseError:
                    i = j = q
                code = scanner.chop(z, 1)
                testCode = code[:i]
                thenCode = code[i + 1:j]
                elseCode = code[j + 1:q]
                catchCode = code[q + 1:z]
                try:
                    result = self.evaluate(testCode, locals)
                    if thenCode:
                        if result:
                            result = self.evaluate(thenCode, locals)
                        else:
                            if elseCode:
                                result = self.evaluate(elseCode, locals)
                            else:
                                result = None
                except SyntaxError:
                    # Don't catch syntax errors; let them through.
                    raise
                except:
                    if catchCode:
                        result = self.evaluate(catchCode, locals)
                    else:
                        raise
                if result is not None:
                    self.stream().write(str(result))
            elif primary == '`':
                # Repr evalulation.
                i = scanner.next('`', 0)
                code = scanner.chop(i, 1)
                self.stream().write(repr(self.evaluate(code, locals)))
            elif primary == ':':
                # In-place expression expansion.
                i = scanner.next(':', 0)
                j = scanner.next(':', i + 1)
                code = scanner.chop(i, j - i + 1)
                self.stream().write("%s:%s:" % (self.prefix, code))
                try:
                    result = self.evaluate(code, locals)
                    if result is not None:
                        self.stream().write(str(result))
                finally:
                    self.stream().write(":")
            elif primary == '[':
                # Conditional and repeated substitution.
                i = scanner.complex('[', ']', 0)
                substitution = scanner.chop(i, 1)
                self.substitute(substitution, locals)
            elif primary == '{':
                # Statement evaluation.
                i = scanner.complex('{', '}', 0)
                code = scanner.chop(i, 1)
                self.execute(code, locals)
            elif primary == self.prefix:
                # A simple character doubling.  As a precaution, check this
                # last in case the prefix has been changed to one of the
                # secondary characters.  This will prevent literal prefixes
                # from appearing in markup, but at least everything else
                # will function as expected!
                self.stream().write(self.prefix)
            else:
                raise ParseError, \
                      "unknown token: %s%s" % (self.prefix, primary)
        except TransientParseError:
            scanner.push(self.prefix + primary)
            raise

    # Low-level evaluation and execution.

    def evaluate(self, expression, locals=None):
        """Evaluate an expression."""
        sys.stdout.push(self.stream())
        try:
            self.invoke('before_evaluate', \
                        expression=expression, locals=locals)
            if locals is not None:
                result = eval(expression, self.globals, locals)
            else:
                result = eval(expression, self.globals)
            self.invoke('after_evaluate')
            return result
        finally:
            sys.stdout.pop()

    def execute(self, statements, locals=None):
        """Execute a statement."""
        if string.find(statements, '\n') < 0:
            statements = string.strip(statements)
        sys.stdout.push(self.stream())
        try:
            self.invoke('before_execute', \
                        statements=statements, locals=locals)
            if locals is not None:
                exec statements in self.globals, locals
            else:
                exec statements in self.globals
            self.invoke('after_execute')
        finally:
            sys.stdout.pop()

    def substitute(self, substitution, locals=None):
        """Do a command substitution."""
        self.invoke('before_substitute', substitution=substitution)
        scanner = Scanner(substitution)
        z = len(substitution)
        i = scanner.next(':', 0, z, True)
        command = string.strip(substitution[:i])
        rest = substitution[i + 1:]
        match = Interpreter.IF_RE.search(command)
        if match is not None:
            # if P : ...
            testCode, = match.groups()
            expansion = rest
            if self.evaluate(testCode, locals):
                result = self.expand(expansion, locals)
                self.stream().write(str(result))
            self.invoke('after_substitute')
            return
        match = Interpreter.WHILE_RE.search(command)
        if match is not None:
            # while P : ...
            testCode, = match.groups()
            expansion = rest
            while 1:
                if not self.evaluate(testCode, locals):
                    break
                result = self.expand(expansion, locals)
                self.stream().write(str(result))
            self.invoke('after_substitute')
            return
        match = Interpreter.FOR_RE.search(command)
        if match is not None:
            # for X in S : ...
            iterator, sequenceCode = match.groups()
            sequence = self.evaluate(sequenceCode, locals)
            expansion = rest
            for element in sequence:
                self.globals[iterator] = element
                result = self.expand(expansion, locals)
                self.stream().write(str(result))
            self.invoke('after_substitute')
            return
        match = Interpreter.MACRO_RE.search(command)
        if match is not None:
            # macro SIGNATURE : ...
            declaration, = match.groups()
            escaped = repr(self.escape(rest))
            code = 'def %s:\n %s\n empy.string(%s, "<macro>", locals())\n' % (declaration, escaped, escaped)
            self.execute(code, locals)
            return
        # If we get here, we didn't find anything.
        raise ParseError, "unknown substitution type"

    def significate(self, key, value):
        """Declare a significator."""
        self.invoke('before_significate', key=key, value=value)
        name = '__%s__' % key
        self.globals[name] = value
        self.invoke('after_significate')

    def finalize(self):
        """Execute any remaining final routines."""
        sys.stdout.push(self.stream())
        try:
            self.finals.reverse()
            for final in self.finals:
                final()
            self.finals = []
        finally:
            sys.stdout.pop()

    # Hooks.

    def invoke(self, hookName, **keywords):
        """Invoke the hook(s) associated with the hook name, should they
        exist."""
        if self.hooks.has_key(hookName):
            for hook in self.hooks[hookName]:
                hook(self, keywords)

    # Error handling.

    def meta(self, exc=None):
        """Construct a MetaError for the interpreter's current state."""
        return MetaError(self.contexts.clone(), exc)

    def handle(self, meta):
        """Handle a MetaError."""
        first = True
        self.invoke('at_handle', meta=meta)
        for context in meta.contexts:
            if first:
                if meta.exc is not None:
                    desc = "error: %s: %s" % (meta.exc.__class__, meta.exc)
                else:
                    desc = "error"
            else:
                desc = "from this context"
            first = False
            sys.stderr.write('%s:%s: %s\n' % \
                             (context.name, context.line, desc))

    def installProxy(self):
        """Install a proxy if necessary."""
        if sys.stdout is sys.__stdout__:
            sys.stdout = ProxyFile(sys.__stdout__)


def environment(name, default=None):
    """Get data from the current environment.  If the default is True
    or False, then presume that we're only interested in the existence
    or non-existence of the environment variable."""
    if os.environ.has_key(name):
        # Do the True/False test by value for future compatibility.
        if default == False or default == True:
            return True
        else:
            return os.environ[name]
    else:
        return default

def usage():
    """Print usage information."""
    sys.stderr.write("""\
Usage: %s [options] [<filename, or '-' for stdin> [<argument>...]]
Welcome to %s version %s.

Valid options:
  -V --version                 Print version and exit
  -h --help                    Print usage and exit
  -k --suppress-errors         Do not exit on errors; continue interactively
  -p --prefix=<char>           Change prefix to something other than @
  -f --flatten                 Flatten the members of pseudmodule to start
  -r --raw --raw-errors        Show raw Python errors
  -i --interactive             Go into interactive mode after processing
  -o --output=<filename>       Specify file for output as write
  -a --append=<filename>       Specify file for output as append
  -P --preprocess=<filename>   Interpret empy file before main processing
  -I --import=<modules>        Import Python modules before processing
  -D --define=<definition>     Execute Python assignment statement
  -E --execute=<statement>     Execute Python statement before processing
  -F --execute-file=<filename> Execute Python file before processing
  -B --buffered-output         Fully buffer output (even open) with -o or -a

The following expansions are supported (where @ is the prefix):
  @# ... NL                    Comment; remove everything up to newline
  @ WHITESPACE                 Remove following whitespace; line continuation
  @\\ ESCAPE_CODE               A C-style escape sequence
  @@                           Literal @; @ is escaped (duplicated prefix)
  @), @], @}                   Literal close parentheses, brackets, braces
  @( EXPRESSION )              Evaluate expression and substitute with str
  @( TEST ? THEN )             If test is true, evaluate then
  @( TEST ? THEN : ELSE )      If test is true, evaluate then, otherwise else
  @( TRY $ CATCH )             Expand try expression, or catch if it raises
  @ SIMPLE_EXPRESSION          Evaluate simple expression and substitute;
                               e.g., @x, @x.y, @f(a, b), @l[i], etc.
  @` EXPRESSION `              Evaluate expression and substitute with repr
  @: EXPRESSION : DUMMY :      Evaluates to @:...:expansion:
  @[ if E : CODE ]             Expand code if expression is true
  @[ while E : CODE ]          Repeatedly expand code while expression is true
  @[ for X in S : CODE ]       Expand code for each element in sequence
  @[ macro SIGNATURE : CODE ]  Define a function as a recallable expansion
  @{ STATEMENTS }              Statements are executed for side effects
  @%% KEY WHITESPACE VALUE NL   Significator form of __KEY__ = VALUE

Valid escape sequences are:
  @\\0                          NUL, null
  @\\a                          BEL, bell
  @\\b                          BS, backspace
  @\\dDDD                       three-digital decimal code DDD
  @\\e                          ESC, escape
  @\\f                          FF, form feed
  @\\h                          DEL, delete
  @\\n                          LF, linefeed, newline
  @\\oOOO                       three-digit octal code OOO
  @\\qQQQQ                      four-digit quaternary code QQQQ
  @\\r                          CR, carriage return
  @\\s                          SP, space
  @\\t                          HT, horizontal tab
  @\\v                          VT, vertical tab
  @\\xHH                        two-digit hexadecimal code HH
  @\\z                          EOT, end of transmission
  @\\^X                         control character ^X

The %s pseudomodule contains the following attributes:
  VERSION                      String representing empy version
  SIGNIFICATOR_RE_STRING       Regular expression string matching significators
  interpreter                  Currently-executing interpreter instance
  argv                         The empy script name and command line arguments
  args                         The command line arguments only
  identify()                   Identify top context as name, line
  setName(name)                Set the name of the current context
  setLine(line)                Set the line number of the current context
  include(file, [loc], [bang]) Include filename or file-like object
  expand(string, [loc])        Explicitly expand string and return
  string(data, [name], [loc])  Process string-like object
  quote(string)                Quote prefixes in provided string and return
  flatten()                    Flatten module contents into globals namespace
  getPrefix()                  Get current prefix
  setPrefix(char)              Set new prefix
  stopDiverting()              Stop diverting; data now sent directly to output
  createDiversion(name)        Create a diversion but do not divert to it
  retrieveDiversion(name)      Retrieve the actual named diversion object
  startDiversion(name)         Start diverting to given diversion
  playDiversion(name)          Recall diversion and then eliminate it
  replayDiversion(name)        Recall diversion but retain it
  purgeDiversion(name)         Erase diversion
  playAllDiversions()          Stop diverting and play all diversions in order
  replayAllDiversions()        Stop diverting and replay all diversions
  purgeAllDiversions()         Stop diverting and purge all diversions
  getFilter()                  Get current filter
  resetFilter()                Reset filter; no filtering
  nullFilter()                 Install null filter
  setFilter(filter)            Install new filter or filter chain
  getHooks(name)               Get the list of hooks with name
  clearHooks(name)             Clear all hooks with name
  addHook(name, hook, [i])     Register hook with name (optionally insert)
  removeHook(name, hook)       Remove hook from name
  invokeHook(name_, ...)       Manually invoke hook with name
  atExit(callable)             Invoke no-argument function at shutdown
  Filter                       The base class for custom filters
  NullFilter                   A filter which never outputs anything
  FunctionFilter               A filter which calls a function
  StringFilter                 A filter which uses a translation mapping
  BufferedFilter               A buffered filter (and base class)
  SizeBufferedFilter           A filter which buffers data into fixed chunks
  LineBufferedFilter           A filter which buffers by lines
  MaximallyBufferedFilter      A filter which buffers everything until close

The following hooks are supported:
  at_shutdown                  Interpreter is shutting down
  at_handle                    Exception is being handled (not thrown)
  before_include               empy.include is starting to execute
  after_include                empy.include is finished executing
  before_expand                empy.expand is starting to execute
  after_expand                 empy.expand is finished executing
  at_quote                     empy.quote is executing
  before_file                  A file-like object is about to be processed
  after_file                   A file-like object is finished processing
  before_string                A standalone string is about to be processed
  after_string                 A standalone string is finished processing
  at_parse                     A parsing pass is being performed
  before_evaluate              A low-level evaluation is about to be done
  after_evaluate               A low-level evaluation has just finished
  before_execute               A low-level execution is about to be done
  after_execute                A low-level execution has just finished
  before_substitute            A @[...] substitution is about to be done
  after_substitute             A @[...] substitution has just finished
  before_significate           A significator is about to be processed
  after_significate            A significator has just finished processing

The following environment variables are recognized (with their command line
equivalents shown):
  EMPY_PREFIX                  Specify the default prefix: -p <value>
  EMPY_FLATTEN                 Flatten empy pseudomodule if defined: -f
  EMPY_RAW                     Show raw errors if defined: -r
  EMPY_INTERACTIVE             Enter interactive mode if defined: -i
  EMPY_BUFFERED_OUTPUT         Fully buffered output if defined: -B

Notes: Whitespace immediately inside parentheses of @(...) are
ignored.  Whitespace immediately inside braces of @{...} are ignored,
unless ... spans multiple lines.  Use @{ ... }@ to suppress newline
following expansion.  Simple expressions ignore trailing dots; `@x.'
means `@(x).'.  A #! at the start of a file is treated as a @#
comment.
""" % (sys.argv[0], __program__, __version__, INTERNAL_MODULE_NAME))

def invoke(args):
    """Run a standalone instance of an empy interpeter."""
    # Initialize the options.
    Output = None
    RawErrors = environment(RAW_ENV, False)
    BufferedOutput = environment(BUFFERED_ENV, False)
    ExitOnError = True
    Preprocessing = []
    Prefix = environment(PREFIX_ENV, DEFAULT_PREFIX)
    Flatten = environment(FLATTEN_ENV, False)
    Interactive = environment(INTERACTIVE_ENV, False)
    # Parse the arguments.
    pairs, remainder = getopt.getopt(args, 'Vhkp:frio:a:P:I:D:E:F:B', ['version', 'help', 'suppress-errors', 'prefix=', 'flatten', 'raw-errors', 'interactive', 'output=' 'append=', 'preprocess=', 'import=', 'define=', 'execute=', 'execute-file=', 'buffered-output'])
    for option, argument in pairs:
        if option in ('-V', '--version'):
            sys.stderr.write("%s version %s\n" % (__program__, __version__))
            return
        elif option in ('-h', '--help'):
            usage()
            return
        elif option in ('-k', '--suppress-errors'):
            ExitOnError = False
            Interactive = True # suppress errors implies interactive mode
        elif option in ('-p', '--prefix'):
            Prefix = argument
        elif option in ('-f', '--flatten'):
            Flatten = True
        elif option in ('-r', '--raw-errors'):
            RawErrors = True
        elif option in ('-i', '--interactive'):
            Interactive = True
        elif option in ('-o', '--output'):
            Output = AbstractFile(argument, 'w', BufferedOutput)
        elif option in ('-a', '--append'):
            Output = AbstractFile(argument, 'a', BufferedOutput)
        elif option in ('-P', '--preprocess'):
            Preprocessing.append(('pre', argument))
        elif option in ('-I', '--import'):
            for module in string.split(argument, ','):
                module = string.strip(module)
                Preprocessing.append(('import', module))
        elif option in ('-D', '--define'):
            Preprocessing.append(('define', argument))
        elif option in ('-E', '--execute'):
            Preprocessing.append(('exec', argument))
        elif option in ('-F', '--execute-file'):
            Preprocessing.append(('file', argument))
        elif option in ('-B', '--buffered-output'):
            BufferedOutput = True
    if not remainder:
        remainder.append('-')
    # Set up the main filename and the argument.
    filename, arguments = remainder[0], remainder[1:]
    # Set up the interpreter.
    if BufferedOutput and Output is None:
        raise CommandLineError, \
              "buffered output only makes sense with -o or -a arguments."
    if len(Prefix) != 1:
        raise CommandLineError, "prefix must be only one character long"
    interpreter = Interpreter(output=Output, argv=remainder, prefix=Prefix)
    if Flatten:
        interpreter.pseudo.flatten()
    try:
        # Execute command-line statements.
        i = 0
        for which, thing in Preprocessing:
            if which == 'pre':
                command = interpreter.file
                target = open(thing, 'r')
                name = thing
            elif which == 'define':
                command = interpreter.string
                if string.find(thing, '=') >= 0:
                    target = '%s{%s}' % (Prefix, thing)
                else:
                    target = '%s{%s = None}' % (Prefix, thing)
                name = '<define:%d>' % i
            elif which == 'exec':
                command = interpreter.string
                target = '%s{%s}' % (Prefix, thing)
                name = '<exec:%d>' % i
            elif which == 'file':
                command = interpreter.string
                name = '<file:%d (%s)>' % (i, thing)
                target = '%s{execfile("""%s""")}' % (Prefix, thing)
            elif which == 'import':
                command = interpreter.string
                name = '<import:%d>' % i
                target = '%s{import %s}' % (Prefix, thing)
            else:
                assert 0
            interpreter.wrap(command, (target, name), \
                             BufferedOutput, RawErrors)
            i = i + 1
        # Start
        if filename == '-':
            if not Interactive:
                name = '<stdin>'
                file = sys.stdin
            else:
                name, file = None, None
        else:
            name = filename
            file = open(filename, 'r')
        if file is not None:
            interpreter.wrap(interpreter.file, (file, name), \
                             BufferedOutput, RawErrors, ExitOnError)
        if Interactive:
            interpreter.interact(BufferedOutput, RawErrors, ExitOnError)
    finally:
        interpreter.shutdown()

def main():
    invoke(sys.argv[1:])

if __name__ == '__main__': main()
