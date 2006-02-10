# $Id$ $Date$

"""
A system for processing Python as markup embedded in text.
"""

__program__ = 'empy'
__version__ = '3.1.1'
__url__ = 'http://www.alcyone.com/software/empy/'
__author__ = 'Erik Max Francis <max@alcyone.com>'
__copyright__ = 'Copyright (C) 2002-2003 Erik Max Francis'
__license__ = 'GPL'


import copy
import getopt
import os
import re
import string
import sys
import types

try:
    # The equivalent of import cStringIO as StringIO.
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
DEFAULT_PSEUDOMODULE_NAME = 'empy'
DEFAULT_SCRIPT_NAME = '?'
SIGNIFICATOR_RE_SUFFIX = r"%(\S+)\s*(.*)\s*$"
SIGNIFICATOR_RE_STRING = DEFAULT_PREFIX + SIGNIFICATOR_RE_SUFFIX
BANGPATH = '#!'
DEFAULT_CHUNK_SIZE = 8192
DEFAULT_ERRORS = 'strict'

# Character information.
IDENTIFIER_FIRST_CHARS = '_abcdefghijklmnopqrstuvwxyz' \
                         'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
IDENTIFIER_CHARS = IDENTIFIER_FIRST_CHARS + '0123456789.'
ENDING_CHARS = {'(': ')', '[': ']', '{': '}'}

# Environment variable names.
OPTIONS_ENV = 'EMPY_OPTIONS'
PREFIX_ENV = 'EMPY_PREFIX'
PSEUDO_ENV = 'EMPY_PSEUDO'
FLATTEN_ENV = 'EMPY_FLATTEN'
RAW_ENV = 'EMPY_RAW_ERRORS'
INTERACTIVE_ENV = 'EMPY_INTERACTIVE'
BUFFERED_ENV = 'EMPY_BUFFERED_OUTPUT'
NO_OVERRIDE_ENV = 'EMPY_NO_OVERRIDE'
UNICODE_ENV = 'EMPY_UNICODE'
INPUT_ENCODING_ENV = 'EMPY_UNICODE_INPUT_ENCODING'
OUTPUT_ENCODING_ENV = 'EMPY_UNICODE_OUTPUT_ENCODING'
INPUT_ERRORS_ENV = 'EMPY_UNICODE_INPUT_ERRORS'
OUTPUT_ERRORS_ENV = 'EMPY_UNICODE_OUTPUT_ERRORS'

# Interpreter options.
BANGPATH_OPT = 'processBangpaths' # process bangpaths as comments?
BUFFERED_OPT = 'bufferedOutput' # fully buffered output?
RAW_OPT = 'rawErrors' # raw errors?
EXIT_OPT = 'exitOnError' # exit on error?
FLATTEN_OPT = 'flatten' # flatten pseudomodule namespace?
OVERRIDE_OPT = 'override' # override sys.stdout with proxy?

# Usage info.
OPTION_INFO = [
("-V --version", "Print version and exit"),
("-h --help", "Print usage and exit"),
("-H --extended-help", "Print extended usage and exit"),
("-k --suppress-errors", "Do not exit on errors; go interactive"),
("-p --prefix=<char>", "Change prefix to something other than @"),
("   --no-prefix", "Do not do any markup processing at all"),
("-m --module=<name>", "Change the internal pseudomodule name"),
("-f --flatten", "Flatten the members of pseudmodule to start"),
("-r --raw-errors", "Show raw Python errors"),
("-i --interactive", "Go into interactive mode after processing"),
("-n --no-override-stdout", "Do not override sys.stdout with proxy"),
("-o --output=<filename>", "Specify file for output as write"),
("-a --append=<filename>", "Specify file for output as append"),
("-b --buffered-output", "Fully buffer output including open"),
("   --binary", "Treat the file as a binary"),
("   --chunk-size=<chunk>", "Use this chunk size for reading binaries"),
("-P --preprocess=<filename>", "Interpret EmPy file before main processing"),
("-I --import=<modules>", "Import Python modules before processing"),
("-D --define=<definition>", "Execute Python assignment statement"),
("-E --execute=<statement>", "Execute Python statement before processing"),
("-F --execute-file=<filename>", "Execute Python file before processing"),
("-u --unicode", "Enable Unicode subsystem (Python 2+ only)"),
("   --unicode-encoding=<e>", "Set both input and output encodings"),
("   --unicode-input-encoding=<e>", "Set input encoding"),
("   --unicode-output-encoding=<e>", "Set output encoding"),
("   --unicode-errors=<E>", "Set both input and output error handler"),
("   --unicode-input-errors=<E>", "Set input error handler"),
("   --unicode-output-errors=<E>", "Set output error handler"),
]

USAGE_NOTES = """\
Notes: Whitespace immediately inside parentheses of @(...) are
ignored.  Whitespace immediately inside braces of @{...} are ignored,
unless ... spans multiple lines.  Use @{ ... }@ to suppress newline
following expansion.  Simple expressions ignore trailing dots; `@x.'
means `@(x).'.  A #! at the start of a file is treated as a @#
comment."""

MARKUP_INFO = [
("@# ... NL", "Comment; remove everything up to newline"),
("@? NAME NL", "Set the current context name"),
("@! INTEGER NL", "Set the current context line number"),
("@ WHITESPACE", "Remove following whitespace; line continuation"),
("@\\ ESCAPE_CODE", "A C-style escape sequence"),
("@@", "Literal @; @ is escaped (duplicated prefix)"),
("@), @], @}", "Literal close parenthesis, bracket, brace"),
("@ STRING_LITERAL", "Replace with string literal contents"),
("@( EXPRESSION )", "Evaluate expression and substitute with str"),
("@( TEST [? THEN [! ELSE]] )", "If test is true, evaluate then, otherwise else"),
("@( TRY $ CATCH )", "Expand try expression, or catch if it raises"),
("@ SIMPLE_EXPRESSION", "Evaluate simple expression and substitute;\n"
                        "e.g., @x, @x.y, @f(a, b), @l[i], etc."),
("@` EXPRESSION `", "Evaluate expression and substitute with repr"),
("@: EXPRESSION : [DUMMY] :", "Evaluates to @:...:expansion:"),
("@{ STATEMENTS }", "Statements are executed for side effects"),
("@[ CONTROL ]", "Control markups: if E; elif E; for N in E;\n"
                 "while E; try; except E, N; finally; continue;\n"
                 "break; end X"),
("@%% KEY WHITESPACE VALUE NL", "Significator form of __KEY__ = VALUE"),
]

ESCAPE_INFO = [
("@\\0", "NUL, null"),
("@\\a", "BEL, bell"),
("@\\b", "BS, backspace"),
("@\\dDDD", "three-digit decimal code DDD"),
("@\\e", "ESC, escape"),
("@\\f", "FF, form feed"),
("@\\h", "DEL, delete"),
("@\\n", "LF, linefeed, newline"),
("@\\N{NAME}", "Unicode character named NAME"),
("@\\oOOO", "three-digit octal code OOO"),
("@\\qQQQQ", "four-digit quaternary code QQQQ"),
("@\\r", "CR, carriage return"),
("@\\s", "SP, space"),
("@\\t", "HT, horizontal tab"),
("@\\uHHHH", "16-bit hexadecimal Unicode HHHH"),
("@\\UHHHHHHHH", "32-bit hexadecimal Unicode HHHHHHHH"),
("@\\v", "VT, vertical tab"),
("@\\xHH", "two-digit hexadecimal code HH"),
("@\\z", "EOT, end of transmission"),
]

PSEUDOMODULE_INFO = [
("VERSION", "String representing EmPy version"),
("SIGNIFICATOR_RE_STRING", "Regular expression matching significators"),
("SIGNIFICATOR_RE_SUFFIX", "The above stub, lacking the prefix"),
("interpreter", "Currently-executing interpreter instance"),
("argv", "The EmPy script name and command line arguments"),
("args", "The command line arguments only"),
("identify()", "Identify top context as name, line"),
("setContextName(name)", "Set the name of the current context"),
("setContextLine(line)", "Set the line number of the current context"),
("atExit(callable)", "Invoke no-argument function at shutdown"),
("getGlobals()", "Retrieve this interpreter's globals"),
("setGlobals(dict)", "Set this interpreter's globals"),
("updateGlobals(dict)", "Merge dictionary into interpreter's globals"),
("clearGlobals()", "Start globals over anew"),
("saveGlobals([deep])", "Save a copy of the globals"),
("restoreGlobals([pop])", "Restore the most recently saved globals"),
("defined(name, [loc])", "Find if the name is defined"),
("evaluate(expression, [loc])", "Evaluate the expression"),
("serialize(expression, [loc])", "Evaluate and serialize the expression"),
("execute(statements, [loc])", "Execute the statements"),
("single(source, [loc])", "Execute the 'single' object"),
("atomic(name, value, [loc])", "Perform an atomic assignment"),
("assign(name, value, [loc])", "Perform an arbitrary assignment"),
("significate(key, [value])", "Significate the given key, value pair"),
("include(file, [loc])", "Include filename or file-like object"),
("expand(string, [loc])", "Explicitly expand string and return"),
("string(data, [name], [loc])", "Process string-like object"),
("quote(string)", "Quote prefixes in provided string and return"),
("flatten([keys])", "Flatten module contents into globals namespace"),
("getPrefix()", "Get current prefix"),
("setPrefix(char)", "Set new prefix"),
("stopDiverting()", "Stop diverting; data sent directly to output"),
("createDiversion(name)", "Create a diversion but do not divert to it"),
("retrieveDiversion(name)", "Retrieve the actual named diversion object"),
("startDiversion(name)", "Start diverting to given diversion"),
("playDiversion(name)", "Recall diversion and then eliminate it"),
("replayDiversion(name)", "Recall diversion but retain it"),
("purgeDiversion(name)", "Erase diversion"),
("playAllDiversions()", "Stop diverting and play all diversions in order"),
("replayAllDiversions()", "Stop diverting and replay all diversions"),
("purgeAllDiversions()", "Stop diverting and purge all diversions"),
("getFilter()", "Get current filter"),
("resetFilter()", "Reset filter; no filtering"),
("nullFilter()", "Install null filter"),
("setFilter(shortcut)", "Install new filter or filter chain"),
("attachFilter(shortcut)", "Attach single filter to end of current chain"),
("enableHooks()", "Enable hooks (default)"),
("disableHooks()", "Disable hook invocation"),
("areHooksEnabled()", "Return whether or not hooks are enabled"),
("getHooks(name)", "Get the list of hooks with name"),
("clearHooks(name)", "Clear all hooks with name"),
("clearAllHooks()", "Clear absolutely all hooks"),
("addHook(name, hook, [i])", "Register hook with name (optionally insert)"),
("removeHook(name, hook)", "Remove hook from name"),
("invokeHook(name_, ...)", "Manually invoke hook with name"),
("Interpreter", "The interpreter class"),
("Filter", "The base class for custom filters"),
("NullFilter", "A filter which never outputs anything"),
("FunctionFilter", "A filter which calls a function"),
("StringFilter", "A filter which uses a translation mapping"),
("BufferedFilter", "A buffered filter (and base class)"),
("SizeBufferedFilter", "A filter which buffers data into fixed chunks"),
("LineBufferedFilter", "A filter which buffers by lines"),
("MaximallyBufferedFilter", "A filter which buffers everything until close"),
]

HOOK_INFO = [
("at_shutdown", "Interpreter is shutting down"),
("at_handle", "Exception is being handled (not thrown)"),
("before_include", "empy.include is starting to execute"),
("after_include", "empy.include is finished executing"),
("before_expand", "empy.expand is starting to execute"),
("after_expand", "empy.expand is finished executing"),
("at_quote", "empy.quote is executing"),
("before_file", "A file-like object is will be processed"),
("after_file", "A file-like object finished processing"),
("before_binary", "A binary file-like object is will processed"),
("after_binary", "A binary file-like object finished processing"),
("before_string", "A standalone string is will be processed"),
("after_string", "A standalone string is finished processing"),
("at_parse", "A parsing pass is being performed"),
("before_evaluate", "A low-level evaluation is will be done"),
("after_evaluate", "A low-level evaluation has just finished"),
("before_execute", "A low-level execution is will be done"),
("after_execute", "A low-level execution has just finished"),
("before_significate", "A significator is will be processed"),
("after_significate", "A significator has just finished processing"),
]

ENVIRONMENT_INFO = [
(OPTIONS_ENV, "Specified options will be included"),
(PREFIX_ENV, "Specify the default prefix: -p <value>"),
(PSEUDO_ENV, "Specify name of pseudomodule: -m <value>"),
(FLATTEN_ENV, "Flatten empy pseudomodule if defined: -f"),
(RAW_ENV, "Show raw errors if defined: -r"),
(INTERACTIVE_ENV, "Enter interactive mode if defined: -i"),
(BUFFERED_ENV, "Fully buffered output if defined: -b"),
(NO_OVERRIDE_ENV, "Do not override sys.stdout if defined: -n"),
(UNICODE_ENV, "Enable Unicode subsystem: -n"),
(INPUT_ENCODING_ENV, "Unicode input encoding"),
(OUTPUT_ENCODING_ENV, "Unicode output encoding"),
(INPUT_ERRORS_ENV, "Unicode input error handler"),
(OUTPUT_ERRORS_ENV, "Unicode output error handler"),
]

class Error(Exception):
    """The base class for all EmPy errors."""
    pass

EmpyError = EmPyError = Error # DEPRECATED

class DiversionError(Error):
    """An error related to diversions."""
    pass

class FilterError(Error):
    """An error related to filters."""
    pass

class StackUnderflowError(Error):
    """A stack underflow."""
    pass

class HookError(Error):
    """An error associated with hooks."""
    pass

class FlowError(Error):
    """An exception related to control flow."""
    pass

class ContinueFlow(FlowError):
    """A continue control flow."""
    pass

class BreakFlow(FlowError):
    """A break control flow."""
    pass

class ParseError(Error):
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
        backtrace = map(lambda x: str(x), self.contexts)
        return "%s: %s (%s)" % (self.exc.__class__, self.exc, \
                                (string.join(backtrace, ', ')))


class Subsystem:

    """The subsystem class defers file creation so that it can create
    Unicode-wrapped files if desired (and possible)."""

    def __init__(self):
        self.useUnicode = False
        self.inputEncoding = None
        self.outputEncoding = None
        self.errors = None

    def initialize(self, inputEncoding=None, outputEncoding=None, \
                   inputErrors=None, outputErrors=None):
        self.useUnicode = True
        try:
            unicode
            import codecs
        except (NameError, ImportError):
            raise Error("Unicode subsystem unavailable")
        defaultEncoding = sys.getdefaultencoding()
        if inputEncoding is None:
            inputEncoding = defaultEncoding
        self.inputEncoding = inputEncoding
        if outputEncoding is None:
            outputEncoding = defaultEncoding
        self.outputEncoding = outputEncoding
        if inputErrors is None:
            inputErrors = DEFAULT_ERRORS
        self.inputErrors = inputErrors
        if outputErrors is None:
            outputErrors = DEFAULT_ERRORS
        self.outputErrors = outputErrors

    def assertUnicode(self):
        if not self.useUnicode:
            raise Error("Unicode subsystem unavailable")

    def open(self, name, mode=None):
        if self.useUnicode:
            return self.unicodeOpen(name, mode)
        else:
            return self.defaultOpen(name, mode)

    def defaultOpen(self, name, mode=None):
        if mode is None:
            mode = 'r'
        return open(name, mode)

    def unicodeOpen(self, name, mode=None):
        import codecs
        if mode is None:
            mode = 'rb'
        if mode.find('w') >= 0 or mode.find('a') >= 0:
            encoding = self.outputEncoding
            errors = self.outputErrors
        else:
            encoding = self.inputEncoding
            errors = self.inputErrors
        return codecs.open(name, mode, encoding, errors)

theSubsystem = Subsystem()


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
            raise StackUnderflowError("stack is empty for top")
        
    def pop(self):
        """Pop the top element off the stack and return it."""
        try:
            return self.data.pop()
        except IndexError:
            raise StackUnderflowError("stack is empty for pop")
        
    def push(self, object):
        """Push an element onto the top of the stack."""
        self.data.append(object)

    def filter(self, function):
        """Filter the elements of the stack through the function."""
        self.data = filter(function, self.data)

    def purge(self):
        """Purge the stack."""
        self.data = []

    def clone(self):
        """Create a duplicate of this stack."""
        return self.__class__(self.data[:])

    def __nonzero__(self): return len(self.data) != 0
    def __len__(self): return len(self.data)
    def __getitem__(self, index): return self.data[-(index + 1)]

    def __repr__(self):
        return '<%s instance at 0x%x [%s]>' % \
               (self.__class__, id(self), \
                string.join(map(repr, self.data), ', '))


class AbstractFile:
    
    """An abstracted file that, when buffered, will totally buffer the
    file, including even the file open."""

    def __init__(self, filename, mode='w', buffered=False):
        self.filename = filename
        self.mode = mode
        self.buffered = buffered
        if buffered:
            self.bufferFile = StringIO.StringIO()
        else:
            self.bufferFile = theSubsystem.open(filename, mode)
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
        if self.buffered:
            file = theSubsystem.open(self.filename, self.mode)
            file.write(self.bufferFile.getvalue())
            file.close()
        else:
            self.bufferFile.close()

    def abort(self):
        if self.buffered:
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

    # These methods are specific to diversions.

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

    def shortcut(self, shortcut):
        """Take a filter shortcut and translate it into a filter, returning
        it.  Sequences don't count here; these should be detected
        independently."""
        if shortcut == 0:
            return NullFilter()
        elif type(shortcut) is types.FunctionType or \
             type(shortcut) is types.BuiltinFunctionType or \
             type(shortcut) is types.BuiltinMethodType or \
             type(shortcut) is types.LambdaType:
            return FunctionFilter(shortcut)
        elif type(shortcut) is types.StringType:
            return StringFilter(filter)
        elif type(shortcut) is types.DictType:
            raise NotImplementedError("mapping filters not yet supported")
        else:
            # Presume it's a plain old filter.
            return shortcut

    def last(self):
        """Find the last filter in the current filter chain, or None if
        there are no filters installed."""
        if self.filter is None:
            return None
        thisFilter, lastFilter = self.filter, None
        while thisFilter is not None and thisFilter is not self.file:
            lastFilter = thisFilter
            thisFilter = thisFilter.next()
        return lastFilter

    def install(self, shortcut=None):
        """Install a new filter; None means no filter.  Handle all the
        special shortcuts for filters here."""
        # Before starting, execute a flush.
        self.filter.flush()
        if shortcut is None or shortcut == [] or shortcut == ():
            # Shortcuts for "no filter."
            self.filter = self.file
        else:
            if type(shortcut) in (types.ListType, types.TupleType):
                shortcuts = list(shortcut)
            else:
                shortcuts = [shortcut]
            # Run through the shortcut filter names, replacing them with
            # full-fledged instances of Filter.
            filters = []
            for shortcut in shortcuts:
                filters.append(self.shortcut(shortcut))
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
                lastFilter = filter.last()
                lastFilter.attach(self.file)
                self.filter = filter

    def attach(self, shortcut):
        """Attached a solitary filter (no sequences allowed here) at the
        end of the current filter chain."""
        lastFilter = self.last()
        if lastFilter is None:
            # Just install it from scratch if there is no active filter.
            self.install(shortcut)
        else:
            # Attach the last filter to this one, and this one to the file.
            filter = self.shortcut(shortcut)
            lastFilter.attach(filter)
            filter.attach(self.file)

    def revert(self):
        """Reset any current diversions."""
        self.currentDiversion = None

    def create(self, name):
        """Create a diversion if one does not already exist, but do not
        divert to it yet."""
        if name is None:
            raise DiversionError("diversion name must be non-None")
        if not self.diversions.has_key(name):
            self.diversions[name] = Diversion()

    def retrieve(self, name):
        """Retrieve the given diversion."""
        if name is None:
            raise DiversionError("diversion name must be non-None")
        if self.diversions.has_key(name):
            return self.diversions[name]
        else:
            raise DiversionError("nonexistent diversion: %s" % name)

    def divert(self, name):
        """Start diverting."""
        if name is None:
            raise DiversionError("diversion name must be non-None")
        self.create(name)
        self.currentDiversion = name

    def undivert(self, name, purgeAfterwards=False):
        """Undivert a particular diversion."""
        if name is None:
            raise DiversionError("diversion name must be non-None")
        if self.diversions.has_key(name):
            diversion = self.diversions[name]
            self.filter.write(diversion.asString())
            if purgeAfterwards:
                self.purge(name)
        else:
            raise DiversionError("nonexistent diversion: %s" % name)

    def purge(self, name):
        """Purge the specified diversion."""
        if name is None:
            raise DiversionError("diversion name must be non-None")
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


class NullFile:

    """A simple class that supports all the file-like object methods
    but simply does nothing at all."""

    def __init__(self): pass
    def write(self, data): pass
    def writelines(self, lines): pass
    def flush(self): pass
    def close(self): pass


class UncloseableFile:

    """A simple class which wraps around a delegate file-like object
    and lets everything through except close calls."""

    def __init__(self, delegate):
        self.delegate = delegate

    def write(self, data):
        self.delegate.write(data)

    def writelines(self, lines):
        self.delegate.writelines(data)

    def flush(self):
        self.delegate.flush()

    def close(self):
        """Eat this one."""
        pass


class ProxyFile:

    """The proxy file object that is intended to take the place of
    sys.stdout.  The proxy can manage a stack of file objects it is
    writing to, and an underlying raw file object."""

    def __init__(self, bottom):
        self.stack = Stack()
        self.bottom = bottom

    def current(self):
        """Get the current stream to write to."""
        if self.stack:
            return self.stack[-1][1]
        else:
            return self.bottom

    def push(self, interpreter):
        self.stack.push((interpreter, interpreter.stream()))

    def pop(self, interpreter):
        result = self.stack.pop()
        assert interpreter is result[0]

    def clear(self, interpreter):
        self.stack.filter(lambda x, i=interpreter: x[0] is not i)

    def write(self, data):
        self.current().write(data)

    def writelines(self, lines):
        self.current().writelines(lines)

    def flush(self):
        self.current().flush()

    def close(self):
        """Close the current file.  If the current file is the bottom, then
        close it and dispose of it."""
        current = self.current()
        if current is self.bottom:
            self.bottom = None
        current.close()

    def _testProxy(self): pass


class Filter:

    """An abstract filter."""

    def __init__(self):
        if self.__class__ is Filter:
            raise NotImplementedError()
        self.sink = None

    def next(self):
        """Return the next filter/file-like object in the sequence, or None."""
        return self.sink

    def write(self, data):
        """The standard write method; this must be overridden in subclasses."""
        raise NotImplementedError()

    def writelines(self, lines):
        """Standard writelines wrapper."""
        for line in lines:
            self.write(line)

    def _flush(self):
        """The _flush method should always flush the sink and should not
        be overridden."""
        self.sink.flush()

    def flush(self):
        """The flush method can be overridden."""
        self._flush()

    def close(self):
        """Close the filter.  Do an explicit flush first, then close the
        sink."""
        self.flush()
        self.sink.close()

    def attach(self, filter):
        """Attach a filter to this one."""
        if self.sink is not None:
            # If it's already attached, detach it first.
            self.detach()
        self.sink = filter

    def detach(self):
        """Detach a filter from its sink."""
        self.flush()
        self._flush() # do a guaranteed flush to just to be safe
        self.sink = None

    def last(self):
        """Find the last filter in this chain."""
        this, last = self, self
        while this is not None:
            last = this
            this = this.next()
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
            raise FilterError("table must be 256-character string")
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
        self._flush()

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


class Context:
    
    """An interpreter context, which encapsulates a name, an input
    file object, and a parser object."""

    DEFAULT_UNIT = 'lines'

    def __init__(self, name, line=0, units=DEFAULT_UNIT):
        self.name = name
        self.line = line
        self.units = units
        self.pause = False

    def bump(self, quantity=1):
        if self.pause:
            self.pause = False
        else:
            self.line = self.line + quantity

    def identify(self):
        return self.name, self.line

    def __str__(self):
        if self.units == self.DEFAULT_UNIT:
            return "%s:%s" % (self.name, self.line)
        else:
            return "%s:%s[%s]" % (self.name, self.line, self.units)


class PseudoModule:
    
    """A pseudomodule for the builtin EmPy routines."""

    # Constants.

    VERSION = __version__
    SIGNIFICATOR_RE_SUFFIX = SIGNIFICATOR_RE_SUFFIX
    SIGNIFICATOR_RE_STRING = None

    # Types.

    Interpreter = None # define this below to prevent a circular reference
    Filter = Filter
    NullFilter = NullFilter
    FunctionFilter = FunctionFilter
    StringFilter = StringFilter
    BufferedFilter = BufferedFilter
    SizeBufferedFilter = SizeBufferedFilter
    LineBufferedFilter = LineBufferedFilter
    MaximallyBufferedFilter = MaximallyBufferedFilter

    def __init__(self, interpreter, name):
        self.interpreter = interpreter
        self.argv = interpreter.argv
        self.args = interpreter.argv[1:]
        self.name = self.__name__ = name
        if interpreter.prefix is None:
            self.SIGNIFICATOR_RE_STRING = None
        else:
            self.SIGNIFICATOR_RE_STRING = interpreter.prefix + \
                                          SIGNIFICATOR_RE_SUFFIX

    # Identification.

    def identify(self):
        """Identify the topmost context with a 2-tuple of the name and
        line number."""
        return self.interpreter.context().identify()

    def atExit(self, callable):
        """Register a function to be called at exit."""
        self.interpreter.finals.append(callable)

    # Context manipulation.

    def pushContext(self, name='<unnamed>', line=0):
        """Create a new context and push it."""
        self.interpreter.contexts.push(Context(name, line))

    def popContext(self):
        """Pop the top context."""
        self.interpreter.contexts.pop()

    def setContextName(self, name):
        """Set the name of the topmost context."""
        context = self.interpreter.context()
        context.name = name
        
    def setContextLine(self, line):
        """Set the name of the topmost context."""
        context = self.interpreter.context()
        context.line = line

    setName = setContextName # DEPRECATED
    setLine = setContextLine # DEPRECATED

    # Globals manipulation.

    def getGlobals(self):
        """Retrieve the globals."""
        return self.interpreter.globals

    def setGlobals(self, globals):
        """Set the globals to the specified dictionary."""
        self.interpreter.globals = globals
        self.interpreter.fix()

    def updateGlobals(self, otherGlobals):
        """Merge another mapping object into this interpreter's globals."""
        self.interpreter.update(otherGlobals)

    def clearGlobals(self):
        """Clear out the globals with a brand new dictionary."""
        self.interpreter.clear()

    def saveGlobals(self, deep=True):
        """Save a copy of the globals off onto the history stack."""
        self.interpreter.save(deep)

    def restoreGlobals(self, destructive=True):
        """Restore the most recently saved copy of the globals."""
        self.interpreter.restore(destructive)
        
    # Hook support.

    def enableHooks(self):
        """Enable hooks."""
        self.interpreter.hooksEnabled = True

    def disableHooks(self):
        """Disable hooks."""
        self.interpreter.hooksEnabled = False

    def areHooksEnabled(self):
        """Return whether or not hooks are presently enabled."""
        if self.interpreter.hooksEnabled is None:
            return True
        else:
            return self.interpreter.hooksEnabled

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

    def clearAllHooks(self):
        """Clear all hooks associated with all names."""
        self.interpreter.hooks = {}

    def addHook(self, name, hook, prepend=False):
        """Add a new hook; optionally insert it rather than appending it."""
        if self.interpreter.hooksEnabled is None:
            # A special optimization so that hooks can be effectively
            # disabled until one is added or they are explicitly turned on.
            self.interpreter.hooksEnabled = True
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
            raise HookError("could not remove hook: %s" % name)

    def invokeHook(self, name_, **keywords):
        """Manually invoke a hook."""
        apply(self.interpreter.invoke, (name_,), keywords)

    # Direct execution.

    def evaluate(self, expression, locals=None):
        """Evaluate the expression."""
        self.interpreter.evaluate(expression, locals)

    def serialize(self, expression, locals=None):
        """Evaluate the expression, serialize it, and write it out to the
        stream, if it is not None."""
        self.interpreter.serialize(expression, locals)

    def defined(self, name, locals=None):
        """Determine whether name appears in the locals or globals."""
        return self.interpreter.defined(name, locals)

    def execute(self, statements, locals=None):
        """Execute the statement(s)."""
        self.interpreter.execute(statements, locals)

    def single(self, source, locals=None):
        """Interpret a 'single' code fragment just as the Python interactive
        interpreter would."""
        self.interpreter.single(source, locals)

    def atomic(self, name, value, locals=None):
        """Do an atomic variable assignment; no tuple unpacking here.
        Note that name is a string but value is a Python object, not a
        string to be evaluated."""
        self.interpreter.atomic(name, value, locals)

    def assign(self, name, value, locals=None):
        """Do a variable assignment, including possible tuple unpacking.
        Name is a string (representing a name or a sequence of names
        separated by commas, and value is a Python object (a sequence of
        the same length if name contains commas)."""
        self.interpreter.assign(name, value, locals)

    def significate(self, key, value=None, locals=None):
        """Do a direct signification."""
        self.interpreter.significate(key, value, locals)

    def import_(self, name, locals=None):
        """Do a Python import."""
        self.interpreter.import_(name, locals)

    # Source manipulation.

    def include(self, fileOrFilename, locals=None):
        """Include a file by filename (if a string) or treat the object
        as a file-like object directly."""
        self.interpreter.include(fileOrFilename, locals)

    def expand(self, data, locals=None):
        """Do an explicit expansion and return its results as a string."""
        return self.interpreter.expand(data, locals)

    def string(self, data, name='<string>', locals=None):
        """Forcibly evaluate an EmPy string."""
        self.interpreter.string(data, name, locals)

    def quote(self, data):
        """Quote the given string so that if expanded by EmPy it would
        evaluate to the original."""
        return self.interpreter.quote(data)

    def escape(self, data, more=''):
        """Escape a string so that nonprintable characters are replaced
        with compatible EmPy expansions."""
        return self.interpreter.escape(data, more)

    def flush(self):
        """Do a manual flush of the underlying stream."""
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

    def setFilter(self, shortcut):
        """Set the filter."""
        self.interpreter.stream().install(shortcut)

    def attachFilter(self, shortcut):
        """Attach a single filter to the end of the current filter chain."""
        self.interpreter.stream().attach(shortcut)


class Token:

    """An element of expansion."""

    def run(self, interpreter, locals):
        raise NotImplementedError()

    def string(self):
        raise NotImplementedError()

    def __str__(self): return self.string()

class NullToken(Token):
    """A chunk of data not containing markups."""
    def __init__(self, data):
        self.data = data

    def run(self, interpreter, locals):
        interpreter.write(self.data)

    def string(self):
        return self.data

class ExpansionToken(Token):
    """A token that involves an expansion."""
    def __init__(self, prefix, first):
        self.prefix = prefix
        self.first = first

    def scan(self, scanner):
        pass

    def run(self, interpreter, locals):
        pass

class WhitespaceToken(ExpansionToken):
    """A whitespace markup."""
    def string(self):
        return '%s%s' % (self.prefix, self.first)

class LiteralToken(ExpansionToken):
    """A literal markup."""
    def run(self, interpreter, locals):
        interpreter.write(self.first)

    def string(self):
        return '%s%s' % (self.prefix, self.first)

class PrefixToken(ExpansionToken):
    """A prefix markup."""
    def run(self, interpreter, locals):
        interpreter.write(interpreter.prefix)

    def string(self):
        return self.prefix * 2
        
class CommentToken(ExpansionToken):
    """A comment markup."""
    def scan(self, scanner):
        loc = scanner.find('\n')
        if loc >= 0:
            self.comment = scanner.chop(loc, 1)
        else:
            raise TransientParseError("comment expects newline")

    def string(self):
        return '%s#%s\n' % (self.prefix, self.comment)

class ContextNameToken(ExpansionToken):
    """A context name change markup."""
    def scan(self, scanner):
        loc = scanner.find('\n')
        if loc >= 0:
            self.name = string.strip(scanner.chop(loc, 1))
        else:
            raise TransientParseError("context name expects newline")

    def run(self, interpreter, locals):
        context = interpreter.context()
        context.name = self.name

class ContextLineToken(ExpansionToken):
    """A context line change markup."""
    def scan(self, scanner):
        loc = scanner.find('\n')
        if loc >= 0:
            try:
                self.line = int(scanner.chop(loc, 1))
            except ValueError:
                raise ParseError("context line requires integer")
        else:
            raise TransientParseError("context line expects newline")

    def run(self, interpreter, locals):
        context = interpreter.context()
        context.line = self.line
        context.pause = True

class EscapeToken(ExpansionToken):
    """An escape markup."""
    def scan(self, scanner):
        try:
            code = scanner.chop(1)
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
                decimalCode = scanner.chop(3)
                result = chr(string.atoi(decimalCode, 10))
            elif code == 'e': # ESC
                result = '\x1b'
            elif code == 'f': # FF
                result = '\x0c'
            elif code == 'h': # DEL
                result = '\x7f'
            elif code == 'n': # LF (newline)
                result = '\x0a'
            elif code == 'N': # Unicode character name
                theSubsystem.assertUnicode()
                import unicodedata
                if scanner.chop(1) != '{':
                    raise ParseError(r"Unicode name escape should be \N{...}")
                i = scanner.find('}')
                name = scanner.chop(i, 1)
                try:
                    result = unicodedata.lookup(name)
                except KeyError:
                    raise Error("unknown Unicode character name: %s" % name)
            elif code == 'o': # octal code
                octalCode = scanner.chop(3)
                result = chr(string.atoi(octalCode, 8))
            elif code == 'q': # quaternary code
                quaternaryCode = scanner.chop(4)
                result = chr(string.atoi(quaternaryCode, 4))
            elif code == 'r': # CR
                result = '\x0d'
            elif code in 's ': # SP
                result = ' '
            elif code == 't': # HT
                result = '\x09'
            elif code in 'u': # Unicode 16-bit hex literal
                theSubsystem.assertUnicode()
                hexCode = scanner.chop(4)
                result = unichr(string.atoi(hexCode, 16))
            elif code in 'U': # Unicode 32-bit hex literal
                theSubsystem.assertUnicode()
                hexCode = scanner.chop(8)
                result = unichr(string.atoi(hexCode, 16))
            elif code == 'v': # VT
                result = '\x0b'
            elif code == 'x': # hexadecimal code
                hexCode = scanner.chop(2)
                result = chr(string.atoi(hexCode, 16))
            elif code == 'z': # EOT
                result = '\x04'
            elif code == '^': # control character
                controlCode = string.upper(scanner.chop(1))
                if controlCode >= '@' and controlCode <= '`':
                    result = chr(ord(controlCode) - ord('@'))
                elif controlCode == '?':
                    result = '\x7f'
                else:
                    raise ParseError("invalid escape control code")
            else:
                raise ParseError("unrecognized escape code")
            assert result is not None
            self.code = result
        except ValueError:
            raise ParseError("invalid numeric escape code")

    def run(self, interpreter, locals):
        interpreter.write(self.code)

    def string(self):
        return '%s\\x%02x' % (self.prefix, ord(self.code))

class SignificatorToken(ExpansionToken):
    """A significator markup."""
    def scan(self, scanner):
        loc = scanner.find('\n')
        if loc >= 0:
            line = scanner.chop(loc, 1)
            if not line:
                raise ParseError("significator must have nonblank key")
            if line[0] in ' \t\v\n':
                raise ParseError("no whitespace between % and key")
            # Work around a subtle CPython-Jython difference by stripping
            # the string before splitting it: 'a '.split(None, 1) has two
            # elements in Jython 2.1).
            fields = string.split(string.strip(line), None, 1)
            if len(fields) == 2 and fields[1] == '':
                fields.pop()
            self.key = fields[0]
            if len(fields) < 2:
                fields.append(None)
            self.key, self.valueCode = fields
        else:
            raise TransientParseError("significator expects newline")

    def run(self, interpreter, locals):
        value = self.valueCode
        if value is not None:
            value = interpreter.evaluate(string.strip(value), locals)
        interpreter.significate(self.key, value)

    def string(self):
        if self.valueCode is None:
            return '%s%%%s\n' % (self.prefix, self.key)
        else:
            return '%s%%%s %s\n' % (self.prefix, self.key, self.valueCode)

class ExpressionToken(ExpansionToken):
    """An expression markup."""
    def scan(self, scanner):
        z = scanner.complex('(', ')', 0)
        try:
            q = scanner.next('$', 0, z, True)
        except ParseError:
            q = z
        try:
            i = scanner.next('?', 0, q, True)
            try:
                j = scanner.next('!', i, q, True)
            except ParseError:
                try:
                    j = scanner.next(':', i, q, True) # DEPRECATED
                except ParseError:
                    j = q
        except ParseError:
            i = j = q
        code = scanner.chop(z, 1)
        self.testCode = code[:i]
        self.thenCode = code[i + 1:j]
        self.elseCode = code[j + 1:q]
        self.exceptCode = code[q + 1:z]

    def run(self, interpreter, locals):
        try:
            result = interpreter.evaluate(self.testCode, locals)
            if self.thenCode:
                if result:
                    result = interpreter.evaluate(self.thenCode, locals)
                else:
                    if self.elseCode:
                        result = interpreter.evaluate(self.elseCode, locals)
                    else:
                        result = None
        except SyntaxError:
            # Don't catch syntax errors; let them through.
            raise
        except:
            if self.exceptCode:
                result = interpreter.evaluate(self.exceptCode, locals)
            else:
                raise
        if result is not None:
            interpreter.write(str(result))

    def string(self):
        result = self.testCode
        if self.thenCode:
            result = result + '?' + self.thenCode
        if self.elseCode:
            result = result + '!' + self.elseCode
        if self.exceptCode:
            result = result + '$' + self.exceptCode
        return '%s(%s)' % (self.prefix, result)

class StringLiteralToken(ExpansionToken):
    """A string token markup."""
    def scan(self, scanner):
        scanner.retreat()
        assert scanner[0] == self.first
        i = scanner.quote()
        self.literal = scanner.chop(i)

    def run(self, interpreter, locals):
        interpreter.literal(self.literal)

    def string(self):
        return '%s%s' % (self.prefix, self.literal)

class SimpleExpressionToken(ExpansionToken):
    """A simple expression markup."""
    def scan(self, scanner):
        i = scanner.simple()
        self.code = self.first + scanner.chop(i)

    def run(self, interpreter, locals):
        interpreter.serialize(self.code, locals)

    def string(self):
        return '%s%s' % (self.prefix, self.code)

class ReprToken(ExpansionToken):
    """A repr markup."""
    def scan(self, scanner):
        i = scanner.next('`', 0)
        self.code = scanner.chop(i, 1)

    def run(self, interpreter, locals):
        interpreter.write(repr(interpreter.evaluate(self.code, locals)))

    def string(self):
        return '%s`%s`' % (self.prefix, self.code)
    
class InPlaceToken(ExpansionToken):
    """An in-place markup."""
    def scan(self, scanner):
        i = scanner.next(':', 0)
        j = scanner.next(':', i + 1)
        self.code = scanner.chop(i, j - i + 1)

    def run(self, interpreter, locals):
        interpreter.write("%s:%s:" % (interpreter.prefix, self.code))
        try:
            interpreter.serialize(self.code, locals)
        finally:
            interpreter.write(":")

    def string(self):
        return '%s:%s::' % (self.prefix, self.code)

class StatementToken(ExpansionToken):
    """A statement markup."""
    def scan(self, scanner):
        i = scanner.complex('{', '}', 0)
        self.code = scanner.chop(i, 1)

    def run(self, interpreter, locals):
        interpreter.execute(self.code, locals)

    def string(self):
        return '%s{%s}' % (self.prefix, self.code)

class ControlToken(ExpansionToken):

    """A control token."""

    PRIMARY_TYPES = ['if', 'for', 'while', 'try', 'def']
    SECONDARY_TYPES = ['elif', 'else', 'except', 'finally']
    TERTIARY_TYPES = ['continue', 'break']
    GREEDY_TYPES = ['if', 'elif', 'for', 'while', 'def', 'end']
    END_TYPES = ['end']

    IN_RE = re.compile(r"\bin\b")
    
    def scan(self, scanner):
        scanner.acquire()
        i = scanner.complex('[', ']', 0)
        self.contents = scanner.chop(i, 1)
        fields = string.split(string.strip(self.contents), ' ', 1)
        if len(fields) > 1:
            self.type, self.rest = fields
        else:
            self.type = fields[0]
            self.rest = None
        self.subtokens = []
        if self.type in self.GREEDY_TYPES and self.rest is None:
            raise ParseError("control '%s' needs arguments" % self.type)
        if self.type in self.PRIMARY_TYPES:
            self.subscan(scanner, self.type)
            self.kind = 'primary'
        elif self.type in self.SECONDARY_TYPES:
            self.kind = 'secondary'
        elif self.type in self.TERTIARY_TYPES:
            self.kind = 'tertiary'
        elif self.type in self.END_TYPES:
            self.kind = 'end'
        else:
            raise ParseError("unknown control markup: '%s'" % self.type)
        scanner.release()

    def subscan(self, scanner, primary):
        """Do a subscan for contained tokens."""
        while True:
            token = scanner.one()
            if token is None:
                raise TransientParseError("control '%s' needs more tokens" % primary)
            if isinstance(token, ControlToken) and \
                   token.type in self.END_TYPES:
                if token.rest != primary:
                    raise ParseError("control must end with 'end %s'" % primary)
                break
            self.subtokens.append(token)

    def build(self, allowed=None):
        """Process the list of subtokens and divide it into a list of
        2-tuples, consisting of the dividing tokens and the list of
        subtokens that follow them.  If allowed is specified, it will
        represent the list of the only secondary markup types which
        are allowed."""
        if allowed is None:
            allowed = SECONDARY_TYPES
        result = []
        latest = []
        result.append((self, latest))
        for subtoken in self.subtokens:
            if isinstance(subtoken, ControlToken) and \
               subtoken.kind == 'secondary':
                if subtoken.type not in allowed:
                    raise ParseError("control unexpected secondary: '%s'" % subtoken.type)
                latest = []
                result.append((subtoken, latest))
            else:
                latest.append(subtoken)
        return result

    def run(self, interpreter, locals):
        interpreter.invoke('before_control', type=self.type, rest=self.rest)
        if self.type == 'if':
            info = self.build(['elif', 'else'])
            elseTokens = None
            if info[-1][0].type == 'else':
                elseTokens = info.pop()[1]
            for secondary, subtokens in info:
                if secondary.type not in ('if', 'elif'):
                    raise ParseError("control 'if' unexpected secondary: '%s'" % secondary.type)
                if interpreter.evaluate(secondary.rest, locals):
                    self.subrun(subtokens, interpreter, locals)
                    break
            else:
                if elseTokens:
                    self.subrun(elseTokens, interpreter, locals)
        elif self.type == 'for':
            sides = self.IN_RE.split(self.rest, 1)
            if len(sides) != 2:
                raise ParseError("control expected 'for x in seq'")
            iterator, sequenceCode = sides
            info = self.build(['else'])
            elseTokens = None
            if info[-1][0].type == 'else':
                elseTokens = info.pop()[1]
            if len(info) != 1:
                raise ParseError("control 'for' expects at most one 'else'")
            sequence = interpreter.evaluate(sequenceCode, locals)
            for element in sequence:
                try:
                    interpreter.assign(iterator, element, locals)
                    self.subrun(info[0][1], interpreter, locals)
                except ContinueFlow:
                    continue
                except BreakFlow:
                    break
            else:
                if elseTokens:
                    self.subrun(elseTokens, interpreter, locals)
        elif self.type == 'while':
            testCode = self.rest
            info = self.build(['else'])
            elseTokens = None
            if info[-1][0].type == 'else':
                elseTokens = info.pop()[1]
            if len(info) != 1:
                raise ParseError("control 'while' expects at most one 'else'")
            atLeastOnce = False
            while True:
                try:
                    if not interpreter.evaluate(testCode, locals):
                        break
                    atLeastOnce = True
                    self.subrun(info[0][1], interpreter, locals)
                except ContinueFlow:
                    continue
                except BreakFlow:
                    break
            if not atLeastOnce and elseTokens:
                self.subrun(elseTokens, interpreter, locals)
        elif self.type == 'try':
            info = self.build(['except', 'finally'])
            if len(info) == 1:
                raise ParseError("control 'try' needs 'except' or 'finally'")
            type = info[-1][0].type
            if type == 'except':
                for secondary, _tokens in info[1:]:
                    if secondary.type != 'except':
                        raise ParseError("control 'try' cannot have 'except' and 'finally'")
            else:
                assert type == 'finally'
                if len(info) != 2:
                    raise ParseError("control 'try' can only have one 'finally'")
            if type == 'except':
                try:
                    self.subrun(info[0][1], interpreter, locals)
                except FlowError:
                    raise
                except Exception, e:
                    for secondary, tokens in info[1:]:
                        exception, variable = interpreter.clause(secondary.rest)
                        if variable is not None:
                            interpreter.assign(variable, e)
                        if isinstance(e, exception):
                            self.subrun(tokens, interpreter, locals)
                            break
                    else:
                        raise
            else:
                try:
                    self.subrun(info[0][1], interpreter, locals)
                finally:
                    self.subrun(info[1][1], interpreter, locals)
        elif self.type == 'continue':
            raise ContinueFlow("control 'continue' without 'for', 'while'")
        elif self.type == 'break':
            raise BreakFlow("control 'break' without 'for', 'while'")
        elif self.type == 'def':
            signature = self.rest
            definition = self.substring()
            code = 'def %s:\n' \
                   ' r"""%s"""\n' \
                   ' return %s.expand(r"""%s""", locals())\n' % \
                   (signature, definition, interpreter.pseudo, definition)
            interpreter.execute(code, locals)
        elif self.type == 'end':
            raise ParseError("control 'end' requires primary markup")
        else:
            raise ParseError("control '%s' cannot be at this level" % self.type)
        interpreter.invoke('after_control')

    def subrun(self, tokens, interpreter, locals):
        """Execute a sequence of tokens."""
        for token in tokens:
            token.run(interpreter, locals)

    def substring(self):
        return string.join(map(str, self.subtokens), '')

    def string(self):
        if self.kind == 'primary':
            return '%s[%s]%s%s[end %s]' % \
                   (self.prefix, self.contents, self.substring(), \
                    self.prefix, self.type)
        else:
            return '%s[%s]' % (self.prefix, self.contents)


class Scanner:

    """A scanner holds a buffer for lookahead parsing and has the
    ability to scan for special symbols and indicators in that
    buffer."""

    # This is the token mapping table that maps first characters to
    # token classes.
    TOKEN_MAP = [
        (None,                   PrefixToken),
        (' \t\v\r\n',            WhitespaceToken),
        (')]}',                  LiteralToken),
        ('\\',                   EscapeToken),
        ('#',                    CommentToken),
        ('?',                    ContextNameToken),
        ('!',                    ContextLineToken),
        ('%',                    SignificatorToken),
        ('(',                    ExpressionToken),
        (IDENTIFIER_FIRST_CHARS, SimpleExpressionToken),
        ('\'\"',                 StringLiteralToken),
        ('`',                    ReprToken),
        (':',                    InPlaceToken),
        ('[',                    ControlToken),
        ('{',                    StatementToken),
    ]

    def __init__(self, prefix, data=''):
        self.prefix = prefix
        self.pointer = 0
        self.buffer = data
        self.lock = 0

    def __nonzero__(self): return self.pointer < len(self.buffer)
    def __len__(self): return len(self.buffer) - self.pointer
    def __getitem__(self, index): return self.buffer[self.pointer + index]

    def __getslice__(self, start, stop):
        if stop > len(self):
            stop = len(self)
        return self.buffer[self.pointer + start:self.pointer + stop]

    def advance(self, count=1):
        """Advance the pointer count characters."""
        self.pointer = self.pointer + count

    def retreat(self, count=1):
        self.pointer = self.pointer - count
        if self.pointer < 0:
            raise ParseError, "can't retreat back over synced out chars"

    def set(self, data):
        """Start the scanner digesting a new batch of data; start the pointer
        over from scratch."""
        self.pointer = 0
        self.buffer = data

    def feed(self, data):
        """Feed some more data to the scanner."""
        self.buffer = self.buffer + data

    def chop(self, count=None, slop=0):
        """Chop the first count + slop characters off the front, and return
        the first count.  If count is not specified, then return
        everything."""
        if count is None:
            assert slop == 0
            count = len(self)
        if count > len(self):
            raise TransientParseError("not enough data to read")
        result = self[:count]
        self.advance(count + slop)
        return result

    def acquire(self):
        """Lock the scanner so it doesn't destroy data on sync."""
        self.lock = self.lock + 1

    def release(self):
        """Unlock the scanner."""
        self.lock = self.lock - 1

    def sync(self):
        """Sync up the buffer with the read head."""
        if self.lock == 0 and self.pointer != 0:
            self.buffer = self.buffer[self.pointer:]
            self.pointer = 0

    def unsync(self):
        """Undo changes; reset the read head."""
        if self.pointer != 0:
            self.lock = 0
            self.pointer = 0

    def rest(self):
        """Get the remainder of the buffer."""
        return self[:]

    def read(self, i=0, count=1):
        """Read count chars starting from i; raise a transient error if
        there aren't enough characters remaining."""
        if len(self) < i + count:
            raise TransientParseError("need more data to read")
        else:
            return self[i:i + count]

    def check(self, i, archetype=None):
        """Scan for the next single or triple quote, with the specified
        archetype.  Return the found quote or None."""
        quote = None
        if self[i] in '\'\"':
            quote = self[i]
            if len(self) - i < 3:
                for j in range(i, len(self)):
                    if self[i] == quote:
                        return quote
                else:
                    raise TransientParseError("need to scan for rest of quote")
            if self[i + 1] == self[i + 2] == quote:
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
            return string.find(self.rest(), sub, start, end)
        else:
            return string.find(self.rest(), sub, start)

    def last(self, char, start=0, end=None):
        """Find the first character that is _not_ the specified character."""
        if end is None:
            end = len(self)
        i = start
        while i < end:
            if self[i] != char:
                return i
            i = i + 1
        else:
            raise TransientParseError("expecting other than %s" % char)

    def next(self, target, start=0, end=None, mandatory=False):
        """Scan for the next occurrence of one of the characters in
        the target string; optionally, make the scan mandatory."""
        if mandatory:
            assert end is not None
        quote = None
        if end is None:
            end = len(self)
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
                c = self[i]
                if quote:
                    if c == '\\':
                        i = i + 1
                else:
                    if c in target:
                        return i
                i = i + 1
        else:
            if mandatory:
                raise ParseError("expecting %s, not found" % target)
            else:
                raise TransientParseError("expecting ending character")

    def quote(self, start=0, end=None, mandatory=False):
        """Scan for the end of the next quote."""
        assert self[start] in '\'\"'
        quote = self.check(start)
        if end is None:
            end = len(self)
        i = start + len(quote)
        while i < end:
            newQuote = self.check(i, quote)
            if newQuote:
                i = i + len(newQuote)
                if newQuote == quote:
                    return i
            else:
                c = self[i]
                if c == '\\':
                    i = i + 1
                i = i + 1
        else:
            if mandatory:
                raise ParseError("expecting end of string literal")
            else:
                raise TransientParseError("expecting end of string literal")

    def nested(self, enter, exit, start=0, end=None):
        """Scan from i for an ending sequence, respecting entries and exits
        only."""
        depth = 0
        if end is None:
            end = len(self)
        i = start
        while i < end:
            c = self[i]
            if c == enter:
                depth = depth + 1
            elif c == exit:
                depth = depth - 1
                if depth < 0:
                    return i
            i = i + 1
        else:
            raise TransientParseError("expecting end of complex expression")

    def complex(self, enter, exit, start=0, end=None, skip=None):
        """Scan from i for an ending sequence, respecting quotes,
        entries and exits."""
        quote = None
        depth = 0
        if end is None:
            end = len(self)
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
                c = self[i]
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
            raise TransientParseError("expecting end of complex expression")

    def word(self, start=0):
        """Scan from i for a simple word."""
        length = len(self)
        i = start
        while i < length:
            if not self[i] in IDENTIFIER_CHARS:
                return i
            i = i + 1
        else:
            raise TransientParseError("expecting end of word")

    def phrase(self, start=0):
        """Scan from i for a phrase (e.g., 'word', 'f(a, b, c)', 'a[i]', or
        combinations like 'x[i](a)'."""
        # Find the word.
        i = self.word(start)
        while i < len(self) and self[i] in '([{':
            enter = self[i]
            if enter == '{':
                raise ParseError("curly braces can't open simple expressions")
            exit = ENDING_CHARS[enter]
            i = self.complex(enter, exit, i + 1) + 1
        return i
    
    def simple(self, start=0):
        """Scan from i for a simple expression, which consists of one 
        more phrases separated by dots."""
        i = self.phrase(start)
        length = len(self)
        while i < length and self[i] == '.':
            i = self.phrase(i)
        # Make sure we don't end with a trailing dot.
        while i > 0 and self[i - 1] == '.':
            i = i - 1
        return i

    def one(self):
        """Parse and return one token, or None if the scanner is empty."""
        if not self:
            return None
        if not self.prefix:
            loc = -1
        else:
            loc = self.find(self.prefix)
        if loc < 0:
            # If there's no prefix in the buffer, then set the location to
            # the end so the whole thing gets processed.
            loc = len(self)
        if loc == 0:
            # If there's a prefix at the beginning of the buffer, process
            # an expansion.
            prefix = self.chop(1)
            assert prefix == self.prefix
            first = self.chop(1)
            if first == self.prefix:
                first = None
            for firsts, factory in self.TOKEN_MAP:
                if firsts is None:
                    if first is None:
                        break
                elif first in firsts:
                    break
            else:
                raise ParseError("unknown markup: %s%s" % (self.prefix, first))
            token = factory(self.prefix, first)
            try:
                token.scan(self)
            except TransientParseError:
                # If a transient parse error occurs, reset the buffer pointer
                # so we can (conceivably) try again later.
                self.unsync()
                raise
        else:
            # Process everything up to loc as a null token.
            data = self.chop(loc)
            token = NullToken(data)
        self.sync()
        return token


class Interpreter:
    
    """An interpreter can process chunks of EmPy code."""

    ESCAPE_CODES = {0x00: '0', 0x07: 'a', 0x08: 'b', 0x1b: 'e', 0x0c: 'f', \
                    0x7f: 'h', 0x0a: 'n', 0x0d: 'r', 0x09: 't', 0x0b: 'v', \
                    0x04: 'z'}

    ASSIGN_TOKEN_RE = re.compile(r"[_a-zA-Z][_a-zA-Z0-9]*|\(|\)|,")

    DEFAULT_OPTIONS = {BANGPATH_OPT: True,
                       BUFFERED_OPT: False,
                       RAW_OPT: False,
                       EXIT_OPT: True,
                       FLATTEN_OPT: False,
                       OVERRIDE_OPT: True}

    _wasProxyInstalled = False # was a proxy installed?

    # Construction, initialization, destruction.

    def __init__(self, output=None, argv=None, prefix=DEFAULT_PREFIX, \
                 pseudo=None, options=None, globals=None):
        # Set up the stream.
        if output is None:
            output = UncloseableFile(sys.__stdout__)
        self.output = output
        self.prefix = prefix
        if pseudo is None:
            pseudo = DEFAULT_PSEUDOMODULE_NAME
        self.pseudo = pseudo
        if argv is None:
            argv = [DEFAULT_SCRIPT_NAME]
        self.argv = argv
        if options is None:
            options = {}
        self.options = options
        # Now set up additional attributes.
        self.hooksEnabled = None # special sentinel meaning "false until added"
        self.hooks = {}
        self.finals = []
        # The interpreter stacks.
        self.contexts = Stack()
        self.streams = Stack()
        # Set up the pseudmodule.
        self.module = PseudoModule(self, pseudo)
        # Now set up the globals.
        self.globals = globals
        self.fix()
        self.history = Stack()
        # Install a proxy stdout if one hasn't been already.
        self.installProxy()
        # Finally, reset the state of all the stacks.
        self.reset()
        # Okay, now flatten the namespaces if that option has been set.
        if self.options.get(FLATTEN_OPT, False):
            self.module.flatten()

    def __del__(self):
        self.shutdown()

    def fix(self):
        """Reset the globals, stamping in the pseudomodule."""
        if self.globals is None:
            self.globals = {}
        # Make sure that there is no collision between two interpreters'
        # globals.
        pseudoName = self.module.__name__
        if self.globals.has_key(pseudoName):
            if self.globals[pseudoName] is not self.module:
                raise Error("interpreter globals collision")
        self.globals[pseudoName] = self.module

    def unfix(self):
        """Remove the pseudomodule (if present) from the globals."""
        UNWANTED_KEYS = [self.pseudo, '__builtins__']
        for unwantedKey in UNWANTED_KEYS:
            if self.globals.has_key(unwantedKey):
                del self.globals[unwantedKey]

    def update(self, other):
        """Update the current globals dictionary with another dictionary."""
        self.globals.update(other)
        self.fix()

    def clear(self):
        """Clear out the globals dictionary with a brand new one."""
        self.globals = {}
        self.fix()

    def save(self, deep=True):
        if deep:
            copyMethod = copy.deepcopy
        else:
            copyMethod = copy.copy
        """Save a copy of the current globals on the history stack."""
        self.unfix()
        self.history.push(copyMethod(self.globals))
        self.fix()

    def restore(self, destructive=True):
        """Restore the topmost historic globals."""
        if destructive:
            fetchMethod = self.history.pop
        else:
            fetchMethod = self.history.top
        self.unfix()
        self.globals = fetchMethod()
        self.fix()

    def shutdown(self):
        """Declare this interpreting session over; close the stream file
        object.  This method is idempotent."""
        if self.streams is not None:
            try:
                self.invoke('at_shutdown')
                self.finalize()
                while self.streams:
                    stream = self.streams.pop()
                    stream.close()
            finally:
                self.streams = None

    def ok(self):
        """Is the interpreter still active?"""
        return self.streams is not None

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
        if self.options.get(OVERRIDE_OPT, True):
            sys.stdout.clear(self)

    def push(self):
        if self.options.get(OVERRIDE_OPT, True):
            sys.stdout.push(self)

    def pop(self):
        if self.options.get(OVERRIDE_OPT, True):
            sys.stdout.pop(self)

    # Higher-level operations.

    def include(self, fileOrFilename, locals=None):
        """Do an include pass on a file or filename."""
        if type(fileOrFilename) is types.StringType:
            # Either it's a string representing a filename ...
            filename = fileOrFilename
            name = filename
            file = theSubsystem.open(filename, 'r')
        else:
            # ... or a file object.
            file = fileOrFilename
            name = "<%s>" % str(file.__class__)
        self.invoke('before_include', name=name, file=file)
        self.file(file, name, locals)
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
        scanner = Scanner(self.prefix, data)
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
        with compatible EmPy expansions."""
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

    def wrap(self, callable, args):
        """Wrap around an application of a callable and handle errors.
        Return whether no error occurred."""
        try:
            apply(callable, args)
            self.reset()
            return True
        except KeyboardInterrupt, e:
            # Handle keyboard interrupts specially: we should always exit
            # from these.
            self.fail(e, True)
        except Exception, e:
            # A standard exception (other than a keyboard interrupt).
            self.fail(e)
        except:
            # If we get here, then either it's an exception not derived from
            # Exception or it's a string exception, so get the error type
            # from the sys module.
            e = sys.exc_type
            self.fail(e)
        # An error occurred if we leak through to here, so do cleanup.
        self.reset()
        return False

    def interact(self):
        """Perform interaction."""
        done = False
        while not done:
            result = self.wrap(self.file, (sys.stdin, '<interact>'))
            if self.options.get(EXIT_OPT, True):
                done = True
            else:
                if result:
                    done = True
                else:
                    self.reset()

    def fail(self, error, fatal=False):
        """Handle an actual error that occurred."""
        if self.options.get(BUFFERED_OPT, False):
            try:
                self.output.abort()
            except AttributeError:
                # If the output file object doesn't have an abort method,
                # something got mismatched, but it's too late to do
                # anything about it now anyway, so just ignore it.
                pass
        meta = self.meta(error)
        self.handle(meta)
        if self.options.get(RAW_OPT, False):
            raise
        if fatal or self.options.get(EXIT_OPT, True):
            sys.exit(FAILURE_CODE)

    def file(self, file, name='<file>', locals=None):
        """Parse the entire contents of a file-like object, line by line."""
        context = Context(name)
        self.contexts.push(context)
        self.invoke('before_file', name=name, file=file)
        scanner = Scanner(self.prefix)
        first = True
        done = False
        while not done:
            self.context().bump()
            line = file.readline()
            if first:
                if self.options.get(BANGPATH_OPT, True) and self.prefix:
                    # Replace a bangpath at the beginning of the first line
                    # with an EmPy comment.
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

    def binary(self, file, name='<binary>', chunkSize=0, locals=None):
        """Parse the entire contents of a file-like object, in chunks."""
        if chunkSize <= 0:
            chunkSize = DEFAULT_CHUNK_SIZE
        context = Context(name, units='bytes')
        self.contexts.push(context)
        self.invoke('before_binary', name=name, file=file, chunkSize=chunkSize)
        scanner = Scanner(self.prefix)
        done = False
        while not done:
            chunk = file.read(chunkSize)
            if chunk:
                scanner.feed(chunk)
            else:
                done = True
            self.safe(scanner, done, locals)
            self.context().bump(len(chunk))
        self.invoke('after_binary')
        self.contexts.pop()

    def string(self, data, name='<string>', locals=None):
        """Parse a string."""
        context = Context(name)
        self.contexts.push(context)
        self.invoke('before_string', name=name, string=data)
        context.bump()
        scanner = Scanner(self.prefix, data)
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
        """Parse and run as much from this scanner as possible."""
        self.invoke('at_parse', scanner=scanner)
        while True:
            token = scanner.one()
            if token is None:
                break
            token.run(self, locals)

    # Medium-level evaluation and execution.

    def significate(self, key, value=None, locals=None):
        """Declare a significator."""
        self.invoke('before_significate', key=key, value=value)
        name = '__%s__' % key
        self.atomic(name, value, locals)
        self.invoke('after_significate')

    def tokenize(self, name):
        """Take an lvalue string and return a name or a (possibly recursive)
        list of names."""
        result = []
        stack = [result]
        for garbage in self.ASSIGN_TOKEN_RE.split(name):
            garbage = string.strip(garbage)
            if garbage:
                raise ParseError("unexpected assignment token: '%s'" % garbage)
        tokens = self.ASSIGN_TOKEN_RE.findall(name)
        # While processing, put a None token at the start of any list in which
        # commas actually appear.
        for token in tokens:
            if token == '(':
                stack.append([])
            elif token == ')':
                top = stack.pop()
                if len(top) == 1:
                    top = top[0] # no None token means that it's not a 1-tuple
                elif top[0] is None:
                    del top[0] # remove the None token for real tuples
                stack[-1].append(top)
            elif token == ',':
                if len(stack[-1]) == 1:
                    stack[-1].insert(0, None)
            else:
                stack[-1].append(token)
        # If it's a 1-tuple at the top level, turn it into a real subsequence.
        if result and result[0] is None:
            result = [result[1:]]
        if len(result) == 1:
            return result[0]
        else:
            return result

    def atomic(self, name, value, locals=None):
        """Do an atomic assignment."""
        if locals is None:
            self.globals[name] = value
        else:
            locals[name] = value

    def multi(self, names, values, locals=None):
        """Do a (potentially recursive) assignment."""
        # No zip in 1.5, so we have to do it manually.
        i = 0
        try:
            values = tuple(values)
        except TypeError:
            raise TypeError("unpack non-sequence")
        if len(names) != len(values):
            raise ValueError("unpack tuple of wrong size")
        for i in range(len(names)):
            name = names[i]
            if type(name) is types.StringType:
                self.atomic(name, values[i], locals)
            else:
                self.multi(name, values[i], locals)

    def assign(self, name, value, locals=None):
        """Do a potentially complex (including tuple unpacking) assignment."""
        left = self.tokenize(name)
        # The return value of tokenize can either be a string or a list of
        # (lists of) strings.
        if type(left) is types.StringType:
            self.atomic(left, value, locals)
        else:
            self.multi(left, value, locals)

    def import_(self, name, locals=None):
        """Do an import."""
        self.execute('import %s' % name, locals)

    def clause(self, catch, locals=None):
        """Given the string representation of an except clause, turn it into
        a 2-tuple consisting of the class name, and either a variable name
        or None."""
        if catch is None:
            exceptionCode, variable = None, None
        elif string.find(catch, ',') >= 0:
            exceptionCode, variable = string.split(string.strip(catch), ',', 1)
            variable = string.strip(variable)
        else:
            exceptionCode, variable = string.strip(catch), None
        if not exceptionCode:
            exception = Exception
        else:
            exception = self.evaluate(exceptionCode, locals)
        return exception, variable

    def serialize(self, expression, locals=None):
        """Do an expansion, involving evaluating an expression, then
        converting it to a string and writing that string to the
        output if the evaluation is not None."""
        result = self.evaluate(expression, locals)
        if result is not None:
            self.write(str(result))

    def defined(self, name, locals=None):
        """Return a Boolean indicating whether or not the name is
        defined either in the locals or the globals."""
        if locals is not None:
            if locals.has_key(name):
                return True
        if self.globals.has_key(name):
            return True
        return False

    def literal(self, text):
        """Process a string literal."""
        ### literal hook
        self.serialize(text)

    # Low-level evaluation and execution.

    def evaluate(self, expression, locals=None):
        """Evaluate an expression."""
        if expression in ('1', 'True'): return True
        if expression in ('0', 'False'): return False
        self.push()
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
            self.pop()

    def execute(self, statements, locals=None):
        """Execute a statement."""
        # If there are any carriage returns (as opposed to linefeeds/newlines)
        # in the statements code, then remove them.  Even on DOS/Windows
        # platforms, 
        if string.find(statements, '\r') >= 0:
            statements = string.replace(statements, '\r', '')
        # If there are no newlines in the statements code, then strip any
        # leading or trailing whitespace.
        if string.find(statements, '\n') < 0:
            statements = string.strip(statements)
        self.push()
        try:
            self.invoke('before_execute', \
                        statements=statements, locals=locals)
            if locals is not None:
                exec statements in self.globals, locals
            else:
                exec statements in self.globals
            self.invoke('after_execute')
        finally:
            self.pop()

    def single(self, source, locals=None):
        """Execute an expression or statement, just as if it were
        entered into the Python interactive interpreter."""
        self.push()
        try:
            self.invoke('before_single', \
                        source=source, locals=locals)
            code = compile(source, '<single>', 'single')
            if locals is not None:
                exec code in self.globals, locals
            else:
                exec code in self.globals
            self.invoke('after_single')
        finally:
            self.pop()

    # Hooks.

    def invoke(self, name_, **keywords):
        """Invoke the hook(s) associated with the hook name, should they
        exist."""
        if self.hooksEnabled and self.hooks.has_key(name_):
            for hook in self.hooks[name_]:
                hook(self, keywords)

    def finalize(self):
        """Execute any remaining final routines."""
        self.push()
        try:
            # Pop them off one at a time so they get executed in reverse
            # order and we remove them as they're executed in case something
            # bad happens.
            while self.finals:
                final = self.finals.pop()
                final()
        finally:
            self.pop()

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
            sys.stderr.write('%s: %s\n' % (context, desc))

    def installProxy(self):
        """Install a proxy if necessary."""
        # Unfortunately, there's no surefire way to make sure that installing
        # a sys.stdout proxy is idempotent, what with different interpreters
        # running from different modules.  The best we can do here is to try
        # manipulating the proxy's test function ...
        try:
            sys.stdout._testProxy()
        except AttributeError:
            # ... if the current stdout object doesn't have one, then check
            # to see if we think _this_ particularly Interpreter class has
            # installed it before ...
            if Interpreter._wasProxyInstalled:
                # ... and if so, we have a proxy problem.
                raise Error("interpreter stdout proxy lost")
            else:
                # Otherwise, install the proxy and set the flag.
                sys.stdout = ProxyFile(sys.stdout)
                Interpreter._wasProxyInstalled = True

PseudoModule.Interpreter = Interpreter # prevent a circular reference


class Document:

    """A representation of an individual EmPy document, as used by a
    processor."""

    def __init__(self, ID, filename):
        self.ID = ID
        self.filename = filename
        self.significators = {}


class Processor:

    """An entity which is capable of processing a hierarchy of EmPy
    files and building a dictionary of document objects associated
    with them describing their significator contents."""

    DEFAULT_EMPY_EXTENSIONS = ('.em',)
    SIGNIFICATOR_RE = re.compile(SIGNIFICATOR_RE_STRING)

    def __init__(self, factory=Document):
        self.factory = factory
        self.documents = {}

    def identifier(self, pathname, filename): return filename

    def clear(self):
        self.documents = {}

    def scan(self, basename, extensions=DEFAULT_EMPY_EXTENSIONS):
        if type(extensions) is types.StringType:
            extensions = (extensions,)
        def _noCriteria(x):
            return True
        def _extensionsCriteria(pathname, extensions=extensions):
            if extensions:
                for extension in extensions:
                    if pathname[-len(extension):] == extension:
                        return True
                return False
            else:
                return True
        self.directory(basename, _noCriteria, _extensionsCriteria, None)
        self.postprocess()

    def postprocess(self):
        pass

    def directory(self, basename, dirCriteria, fileCriteria, depth=None):
        if depth is not None:
            if depth <= 0:
                return
            else:
                depth = depth - 1
        filenames = os.listdir(basename)
        for filename in filenames:
            pathname = os.path.join(basename, filename)
            if os.path.isdir(pathname):
                if dirCriteria(pathname):
                    self.directory(pathname, dirCriteria, fileCriteria, depth)
            elif os.path.isfile(pathname):
                if fileCriteria(pathname):
                    documentID = self.identifier(pathname, filename)
                    document = self.factory(documentID, pathname)
                    self.file(document, open(pathname))
                    self.documents[documentID] = document

    def file(self, document, file):
        while True:
            line = file.readline()
            if not line:
                break
            self.line(document, line)

    def line(self, document, line):
        match = self.SIGNIFICATOR_RE.search(line)
        if match:
            key, valueS = match.groups()
            valueS = string.strip(valueS)
            if valueS:
                value = eval(valueS)
            else:
                value = None
            document.significators[key] = value


def expand(_data, _globals=None, \
           _argv=None, _prefix=DEFAULT_PREFIX, _pseudo=None, _options=None, \
           **_locals):
    """Do an atomic expansion of the given source data, creating and
    shutting down an interpreter dedicated to the task.  The sys.stdout
    object is saved off and then replaced before this function
    returns."""
    if len(_locals) == 0:
        # If there were no keyword arguments specified, don't use a locals
        # dictionary at all.
        _locals = None
    output = NullFile()
    interpreter = Interpreter(output, argv=_argv, prefix=_prefix, \
                              pseudo=_pseudo, options=_options, \
                              globals=_globals)
    if interpreter.options.get(OVERRIDE_OPT, True):
        oldStdout = sys.stdout
    try:
        result = interpreter.expand(_data, _locals)
    finally:
        interpreter.shutdown()
        if _globals is not None:
            interpreter.unfix() # remove pseudomodule to prevent clashes
        if interpreter.options.get(OVERRIDE_OPT, True):
            sys.stdout = oldStdout
    return result

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

def info(table):
    DEFAULT_LEFT = 28
    maxLeft = 0
    maxRight = 0
    for left, right in table:
        if len(left) > maxLeft:
            maxLeft = len(left)
        if len(right) > maxRight:
            maxRight = len(right)
    FORMAT = '  %%-%ds  %%s\n' % max(maxLeft, DEFAULT_LEFT)
    for left, right in table:
        if right.find('\n') >= 0:
            for right in right.split('\n'):
                sys.stderr.write(FORMAT % (left, right))
                left = ''
        else:
            sys.stderr.write(FORMAT % (left, right))

def usage(verbose=True):
    """Print usage information."""
    programName = sys.argv[0]
    def warn(line=''):
        sys.stderr.write("%s\n" % line)
    warn("""\
Usage: %s [options] [<filename, or '-' for stdin> [<argument>...]]
Welcome to EmPy version %s.""" % (programName, __version__))
    warn()
    warn("Valid options:")
    info(OPTION_INFO)
    if verbose:
        warn()
        warn("The following markups are supported:")
        info(MARKUP_INFO)
        warn()
        warn("Valid escape sequences are:")
        info(ESCAPE_INFO)
        warn()
        warn("The %s pseudomodule contains the following attributes:" % \
             DEFAULT_PSEUDOMODULE_NAME)
        info(PSEUDOMODULE_INFO)
        warn()
        warn("The following hooks are supported:")
        info(HOOK_INFO)
        warn()
        warn("The following environment variables are recognized:")
        info(ENVIRONMENT_INFO)
        warn()
        warn(USAGE_NOTES)
    else:
        warn()
        warn("Type %s -H for more extensive help." % programName)

def invoke(args):
    """Run a standalone instance of an EmPy interpeter."""
    # Initialize the options.
    _output = None
    _options = {BUFFERED_OPT: environment(BUFFERED_ENV, False),
                RAW_OPT: environment(RAW_ENV, False),
                EXIT_OPT: True,
                FLATTEN_OPT: environment(FLATTEN_ENV, False),
                OVERRIDE_OPT: not environment(NO_OVERRIDE_ENV, False)}
    _preprocessing = []
    _prefix = environment(PREFIX_ENV, DEFAULT_PREFIX)
    _pseudo = environment(PSEUDO_ENV, None)
    _interactive = environment(INTERACTIVE_ENV, False)
    _extraArguments = environment(OPTIONS_ENV)
    _binary = -1 # negative for not, 0 for default size, positive for size
    _unicode = environment(UNICODE_ENV, False)
    _unicodeInputEncoding = environment(INPUT_ENCODING_ENV, None)
    _unicodeOutputEncoding = environment(OUTPUT_ENCODING_ENV, None)
    _unicodeInputErrors = environment(INPUT_ERRORS_ENV, None)
    _unicodeOutputErrors = environment(OUTPUT_ERRORS_ENV, None)
    _pauseAtEnd = False
    if _extraArguments is not None:
        _extraArguments = string.split(_extraArguments)
        args = _extraArguments + args
    # Parse the arguments.
    pairs, remainder = getopt.getopt(args, 'VhHkp:m:frino:a:buBP:I:D:E:F:', ['version', 'help', 'extended-help', 'suppress-errors', 'prefix=', 'no-prefix', 'module=', 'flatten', 'raw-errors', 'interactive', 'no-override-stdout', 'binary', 'chunk-size=', 'output=' 'append=', 'preprocess=', 'import=', 'define=', 'execute=', 'execute-file=', 'buffered-output', 'unicode', 'unicode-encoding=', 'unicode-input-encoding=', 'unicode-output-encoding=', 'unicode-errors=', 'unicode-input-errors=', 'unicode-output-errors=', 'pause-at-end'])
    for option, argument in pairs:
        if option in ('-V', '--version'):
            sys.stderr.write("%s version %s\n" % (__program__, __version__))
            return
        elif option in ('-h', '--help'):
            usage(False)
            return
        elif option in ('-H', '--extended-help'):
            usage(True)
            return
        elif option in ('-k', '--suppress-errors'):
            _options[EXIT_OPT] = False
            _interactive = True # suppress errors implies interactive mode
        elif option in ('-m', '--module'):
            _pseudo = argument
        elif option in ('-f', '--flatten'):
            _options[FLATTEN_OPT] = True
        elif option in ('-p', '--prefix'):
            _prefix = argument
        elif option in ('--no-prefix',):
            _prefix = None
        elif option in ('-r', '--raw-errors'):
            _options[RAW_OPT] = True
        elif option in ('-i', '--interactive'):
            _interactive = True
        elif option in ('-n', '--no-override-stdout'):
            _options[OVERRIDE_OPT] = False
        elif option in ('-o', '--output'):
            _output = argument, 'w', _options[BUFFERED_OPT]
        elif option in ('-a', '--append'):
            _output = argument, 'a', _options[BUFFERED_OPT]
        elif option in ('-b', '--buffered-output'):
            _options[BUFFERED_OPT] = True
        elif option in ('-B',): # DEPRECATED
            _options[BUFFERED_OPT] = True
        elif option in ('--binary',):
            _binary = 0
        elif option in ('--chunk-size',):
            _binary = int(argument)
        elif option in ('-P', '--preprocess'):
            _preprocessing.append(('pre', argument))
        elif option in ('-I', '--import'):
            for module in string.split(argument, ','):
                module = string.strip(module)
                _preprocessing.append(('import', module))
        elif option in ('-D', '--define'):
            _preprocessing.append(('define', argument))
        elif option in ('-E', '--execute'):
            _preprocessing.append(('exec', argument))
        elif option in ('-F', '--execute-file'):
            _preprocessing.append(('file', argument))
        elif option in ('-u', '--unicode'):
            _unicode = True
        elif option in ('--unicode-encoding',):
            _unicodeInputEncoding = _unicodeOutputEncoding = argument
        elif option in ('--unicode-input-encoding',):
            _unicodeInputEncoding = argument
        elif option in ('--unicode-output-encoding',):
            _unicodeOutputEncoding = argument
        elif option in ('--unicode-errors',):
            _unicodeInputErrors = _unicodeOutputErrors = argument
        elif option in ('--unicode-input-errors',):
            _unicodeInputErrors = argument
        elif option in ('--unicode-output-errors',):
            _unicodeOutputErrors = argument
        elif option in ('--pause-at-end',):
            _pauseAtEnd = True
    # Set up the Unicode subsystem if required.
    if _unicode or \
           _unicodeInputEncoding or _unicodeOutputEncoding or \
           _unicodeInputErrors or _unicodeOutputErrors:
        theSubsystem.initialize(_unicodeInputEncoding, \
                                _unicodeOutputEncoding, \
                                _unicodeInputErrors, _unicodeOutputErrors)
    # Now initialize the output file if something has already been selected.
    if _output is not None:
        _output = apply(AbstractFile, _output)
    # Set up the main filename and the argument.
    if not remainder:
        remainder.append('-')
    filename, arguments = remainder[0], remainder[1:]
    # Set up the interpreter.
    if _options[BUFFERED_OPT] and _output is None:
        raise ValueError("-b only makes sense with -o or -a arguments.")
    if _prefix == 'None':
        _prefix = None
    if _prefix and type(_prefix) is types.StringType and len(_prefix) != 1:
        raise Error("prefix must be single-character string")
    interpreter = Interpreter(_output, remainder, _prefix, _pseudo, _options)
    try:
        # Execute command-line statements.
        i = 0
        for which, thing in _preprocessing:
            if which == 'pre':
                command = interpreter.file
                target = theSubsystem.open(thing, 'r')
                name = thing
            elif which == 'define':
                command = interpreter.string
                if string.find(thing, '=') >= 0:
                    target = '%s{%s}' % (_prefix, thing)
                else:
                    target = '%s{%s = None}' % (_prefix, thing)
                name = '<define:%d>' % i
            elif which == 'exec':
                command = interpreter.string
                target = '%s{%s}' % (_prefix, thing)
                name = '<exec:%d>' % i
            elif which == 'file':
                command = interpreter.string
                name = '<file:%d (%s)>' % (i, thing)
                target = '%s{execfile("""%s""")}' % (_prefix, thing)
            elif which == 'import':
                command = interpreter.string
                name = '<import:%d>' % i
                target = '%s{import %s}' % (_prefix, thing)
            else:
                assert 0
            interpreter.wrap(command, (target, name))
            i = i + 1
        # Now process the primary file.
        if filename == '-':
            if not _interactive:
                name = '<stdin>'
                file = sys.stdin
            else:
                name, file = None, None
        else:
            name = filename
            file = theSubsystem.open(filename, 'r')
        if file is not None:
            if _binary < 0:
                interpreter.wrap(interpreter.file, (file, name))
            else:
                chunkSize = _binary
                interpreter.wrap(interpreter.binary, (file, name, chunkSize))
        # If we're supposed to go interactive afterwards, do it.
        if _interactive:
            interpreter.interact()
    finally:
        interpreter.shutdown()
    # Finally, if we should pause at the end, do it.
    if _pauseAtEnd:
        try:
            raw_input()
        except EOFError:
            pass

def main():
    invoke(sys.argv[1:])

if __name__ == '__main__': main()
