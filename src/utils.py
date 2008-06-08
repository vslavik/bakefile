#
#  This file is part of Bakefile (http://www.bakefile.org)
#
#  Copyright (C) 2003-2008 Vaclav Slavik
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
#  Misc utility functions for use in Bakefiles
#

import sys, os, os.path, string, glob
if sys.version_info < (2,4):
    from sets import Set as set

import mk, errors, config
import containers
import dependencies

def checkBakefileVersion(version):
    """Returns true iff current bakefile version is at least 'version'.
       'version' is string with three numbers separated with dots,
       e.g. '0.1.4'."""
    vcur = mk.vars['BAKEFILE_VERSION'].split('.')
    vreq = version.split('.')
    return vcur >= vreq

def isoption(name):
    return name in mk.options

def iscondvar(name):
    return name in mk.cond_vars

def isdefined(name):
    return (name in mk.__curNamespace or
            # names of options and condvars are not in the current namespace
            # if we're evaluating a constant expression, but this function
            # must work correctly even in that case, so we have to test for
            # options and condvars explicitly:
            isoption(name) or iscondvar(name))

def isconst(expr):
    try:
        mk.evalExpr(expr, use_options=0)
        return True
    except NameError:
        return False

def ifthenelse(cond, iftrue, iffalse):
    if eval(str(cond)): return iftrue
    else: return iffalse

def envvar(name):
    if mk.vars['FORMAT'] == 'watcom':
        return '$(DOLLAR)(%%%s)' % name
    else:
        return '$(DOLLAR)(%s)' % name


__refEval = 0
__refContexts = {}

def ref(var, target=None, context=None):
    if __refEval:
        if context != None:
            context = __refContexts[context]
        if target != None and target not in mk.targets:
            raise errors.Error("target '%s' cannot be used in ref() since it doesn't exist" % target,
                               context=context)
        try:
            if target == None or var not in mk.targets[target].vars:
                return mk.vars[var]
            else:
                return mk.targets[target].vars[var]
        except KeyError:
            if target == None:
                raise errors.Error("undefined variable '%s'" % var,
                                   context=context)
            else:
                raise errors.Error("undefined variable '%s' on target '%s'" % (var, target),
                                   context=context)
    else:
        if mk.__trackUsage: mk.__usageTracker.refs += 1
        if context == None:
            context = len(__refContexts)
            __refContexts[context] = errors.getCtx()
        if target == None:
            return "$(ref('%s',None,%i))" % (var, context)
        else:
            return "$(ref('%s','%s',%i))" % (var, target, context)

deadTargets = []
def isDeadTarget(target):
    return target in deadTargets


def makeUniqueCondVarName(name):
    """Creates name for cond. var."""
    n = nb = '__%s' % (name.replace('-','_').replace('.','_').replace('/','_'))
    i = 1
    while n in mk.cond_vars:
        n = '%s_%i' % (nb, i)
        i += 1
    return n


substVarNameCounter = 0

__substituteCallbacks = {}

def addSubstituteCallback(varname, function):
    """Register callback for substitute() and substitute2() functions.
       This callback is used if (and _only_ if) other methods of substitution
       fail, in particular when an option is found during substitution.
       
       'function' takes four arguments: (varname, callback, caller)
       where 'callback' is the original callback function that was passed as
       substitute()'s argument, 'cond' is 'cond' argument passed to substitue2,
       'varname' is variable name and 'caller' is same as 'caller' passed to
       substitute(2).

       If the function returns None, next function in the chain is called;
       otherwise returned string is used as substitution result.
    """
    if varname in __substituteCallbacks:
        __substituteCallbacks[varname] = [function] + __substituteCallbacks[varname]
    else:
        __substituteCallbacks[varname] = [function]

def substitute2(str, callback, desc=None, cond=None, hints='', caller=None):
    """Same as substitute, but the callbacks takes two arguments (text and
       condition object) instead of one."""

    if caller == None:
        caller = 'substitute2'

    if desc == None:
        global substVarNameCounter
        desc = '%i' % substVarNameCounter
        substVarNameCounter += 1
    
    def callbackVar(cnd, expr, use_options, target, add_dict):
        if expr in mk.cond_vars:
            cond = mk.cond_vars[expr]
            var = mk.CondVar(makeUniqueCondVarName('%s_%s' % (cond.name, desc)))
            mk.addCondVar(var, hints)
            for v in cond.values:
                cond2 = mk.mergeConditions(cnd, v.cond)
                if '$' in v.value:
                    var.add(v.cond,
                            substitute2(v.value, callback, desc, cond2, hints))
                else:
                    if len(v.value) == 0 or v.value.isspace():
                        var.add(v.cond, v.value)
                    else:
                        var.add(v.cond, callback(cond2, v.value))
            return '$(%s)' % var.name

        if expr in mk.options and mk.options[expr].values != None:
            opt = mk.options[expr]
            var = mk.CondVar(makeUniqueCondVarName('%s_%s' % (opt.name, desc)))
            mk.addCondVar(var, hints)
            for v in opt.values:
                cond = mk.makeCondition("%s=='%s'" % (opt.name, v))
                cond2 = mk.mergeConditions(cnd, cond)
                if '$' in v:
                    var.add(cond, substitute2(v, callback, desc, cond2, hints))
                else:
                    if len(v) == 0 or v.isspace(): var.add(cond, v)
                    else: var.add(cond, callback(cond2, v))
            return '$(%s)' % var.name

        if expr in __substituteCallbacks:
            for func in __substituteCallbacks[expr]:
                rval = func(expr, callback, caller)
                if rval != None:
                    return rval
        raise errors.Error("'%s' can't be used in this context, "%expr +
                 "not a conditional variable or option with listed values")

    def callbackTxt(cond, expr):
        if len(expr) == 0 or expr.isspace(): return expr
        return callback(cond, expr)
    
    return mk.__doEvalExpr(str, callbackVar, callbackTxt,
                           cond, # moreArgs
                           1,    # use_options
                           None, # target
                           None) # add_dict


def substitute(str, callback, desc=None, hints='', caller='substitute'):
    """Calls callback to substitute text in str by something else. Works with
       conditional variables, too."""
    def callb(cond, s):
        return callback(s)
    if caller == None:
        caller = 'substitute'
    return substitute2(str, callb, desc, hints=hints, caller=caller)


def substituteFromDict(str, dict, desc=None):
    """Like substitute(), but less generic: instead of calling callback, the
       text is looked up in a dictionary. This imposes the restriction that
       'str' may be only single word."""

    def _getValue(x):
        try:
            return dict[x]
        except KeyError:
            raise errors.Error(
                    "value '%s' not allowed in this context: not one of %s" %
                    (x, dict.keys()))
    return substitute(str, _getValue, desc)


def getPossibleValues(expr):
    """Attempts to get all possible values of 'str' expansion.

       For now, this function assumes that variable parts (condvars references)
       are separated from other parts with whitespace.

       Returns generator for list of values as split on whitespace.
    """
    # FIXME: see docstring

    def callbackVar(nothing, expr, use_options, target, add_dict):
        ret = []
        if expr in mk.cond_vars:
            cond = mk.cond_vars[expr]
            for v in cond.values:
                if '$' in v.value:
                    ret += getPossibleValues(v.value)
                else:
                    ret.append(v.value)
            return ' '.join(ret)

        if expr in mk.options and mk.options[expr].values != None:
            opt = mk.options[expr]
            for v in opt.values:
                if '$' in v.value:
                    ret += getPossibleValues(v)
                else:
                    ret.append(v)
            return ' '.join(ret)

        # don't know what else to try, return as-is
        return expr

    def callbackTxt(nothing, expr):
        return expr

    return mk.__doEvalExpr(expr, callbackVar, callbackTxt,
                           None, 1, None, None).split()


def nativePaths(filenames):
    """Translates filenames from Unix to native filenames."""
    if mk.vars['TOOLSET'] == 'unix':
        return filenames
    else:
        return substitute(filenames,
                          lambda x: x.replace('/', mk.vars['DIRSEP']),
                          'FILENAMES',
                          caller='nativePaths')

def currentosPaths(filenames):
    """
       Translates filenames from the Unix-style format (which is also the
       Bakefile-style!) to the format for the OS running at bake-time.
       This utility should be used in all functions which perform some kind of
       tests on files/directories at bake-time.
    """
    nativeSep = mk.vars['DIRSEP']
    if nativeSep == os.sep:
        return filenames
    else:
        return substitute(filenames,
                          lambda x: x.replace(nativeSep, os.sep),
                          'FILENAMES',
                          caller='currentosPaths')

def findSources(filenames):
    """Adds source filename prefix to files."""
    return substitute(filenames,
                      lambda x: '%s%s%s' % \
                             (nativePaths(mk.vars['SRCDIR']), mk.vars['DIRSEP'], x),
                      'SOURCEFILES')

def safeMakefileValue(s):
    # some makes (e.g. dmars's smake) don't like '-' character, because it has
    # another meaning; substitute it here
    return s.replace('-','_').replace('.','_')


allObjectsBasenames = {}

def getObjectName(source, target, ext, objSuffix=''):

    allNames = allObjectsBasenames[target]
    dirsep = mk.vars['DIRSEP']

    def _makeUniqueName(name, all):
        """Finds the shortest path suffix that is unique in given set."""
        assert name in all
        split = name.split(dirsep)
        # try adding path components
        for i in range(2, len(split)+1):
            x = dirsep.join(split[-i:])
            conflicts = len([n for n in all if n.endswith(x)])
            if conflicts == 1: # only this one
                return x.replace(dirsep, '_')
        raise errors.Error("don't know how to create object file name for \"%s\"" % name)

    pos = source.rfind('.')
    srcext = source[pos:]
    noext = source[:pos]
    pos = max(noext.rfind('/'), noext.rfind(dirsep))
    base = noext[pos+1:]

    # if the same basename is used by more objects (see bug #92), create
    # longer-but-unique object names:
    if base in allNames and len(allNames[base]) > 1:
        base = _makeUniqueName(noext, allNames[base])

    base = safeMakefileValue(base)

    objdir = mkPathPrefix(mk.vars['BUILDDIR'])
    objname = '%s%s_%s%s%s' % (objdir,
                               safeMakefileValue(mk.targets[target].id),
                               base,
                               objSuffix,
                               ext)
    return objname


def sources2objects(sources, target, ext, objSuffix=''):
    """Adds rules to compile object files from source files listed in
       'sources', when compiling target 'target', with object files extension
       being 'ext'. Optional 'objSuffix' argument is used to change the name
       of object file (e.g. to compile foo.c to foo_rc.o instead of foo.o).

       Returns object files list."""
    import reader, xmlparser
    
    # It's a bit faster (about 10% on wxWindows makefiles) to not parse XML
    # but construct the elements tree by hand. We construc the tree for this
    # code:
    #
    #code = """
    #<makefile>
    #<%s id="%s" category="automatic">
    #    <parent-target>%s</parent-target>
    #    <dst>%s</dst>
    #    <src>%s</src>
    #</%s>
    #</makefile>"""
    cRoot = xmlparser.Element()
    cTarget = xmlparser.Element()
    cTarget.props['category'] = 'automatic'
    cSrc = xmlparser.Element()
    cDst = xmlparser.Element()
    cParent = xmlparser.Element()
    cRoot.name = 'makefile'
    cRoot.children = [cTarget]
    cRoot.value = ''
    cTarget.children = [cParent,cSrc,cDst]
    cParent.name = 'parent-target'
    cTarget.value = ''
    cSrc.name = 'src'
    cDst.name = 'dst'
    cParent.value = target

    files = containers.OrderedDict()

    sources2 = nativePaths(sources)

    # used to resolve conflicting names, see http://www.bakefile.org/ticket/92:
    # key: basename, value: set of full names w/o extension
    if target not in allObjectsBasenames:
        allObjectsBasenames[target] = {}
    basenames = allObjectsBasenames[target]
    dirsep = mk.vars['DIRSEP']
    for s in getPossibleValues(sources):
        full = s[:s.rfind('.')]
        base = full[full.rfind(dirsep)+1:]
        if base not in basenames:
            basenames[base] = set()
        basenames[base].add(full)

    def callback_objnames(cond, sources):
        prefix = suffix = ''
        if sources[0].isspace(): prefix=' '
        if sources[-1].isspace(): suffix=' '
        retval = []
        for s in sources.split():
            objname = getObjectName(s, target, ext, objSuffix)
            if objname in files:
                files[objname].append((s,cond))
            else:
                files[objname] = [(s,cond)]
            retval.append(objname)
        return '%s%s%s' % (prefix, ' '.join(retval), suffix)
            
    def addRule(id, obj, src, cond):
        srcext = src.split('.')[-1]
        rule = '__%s-to-%s' % (srcext, ext[1:])

        # provide understandable message in case of unknown extension:
        if not rule in reader.HANDLERS:
            raise errors.Error(
            'unable to generate rule for compilation of *.%s files' % srcext)
        
        cTarget.name = rule
        cTarget.props['id'] = id
        cSrc.value = src
        cDst.value = obj
        reader.processXML(cRoot)
        # CAUTION! A hack to disable creating unneeded variables:
        #          We don't pass condition as part of target's XML
        #          specification because that would create __depname
        #          conditional variable and we don't need it
        mk.targets[id].cond = cond

    def reduceConditions(cond1, cond2):
        """Reduces conditions:
             1) A & B, A & notB  |- A
             2) A, A & B         |- A
        """

        all = containers.OrderedDict()
        values = {}
        for e in cond1.exprs:
            all[e.option] = e
        for e in cond2.exprs:
            if e.option in all:
                if e.value == all[e.option].value:
                    values[e.option] = all[e.option].value
                    all[e.option] = True
                elif e.value != all[e.option].value and \
                     e.option.values != None and len(e.option.values) == 2:
                    all[e.option] = False
                else:
                    return None
            else:
                return None
        ret = []
        for e in all:
            if all[e] is False:
                pass
            elif all[e] is True:
                ret.append("%s=='%s'" % (e.name, values[e]))
            else:
                return None                
        if len(ret) == 0:
            return '1'
        else:
            return mk.makeCondition(' and '.join(ret))
 
    retval = substitute2(sources2, callback_objnames, 'OBJECTS', hints='files')

    easyFiles = []
    hardFiles = []
    for f in files:
        if len(files[f]) == 1:
            easyFiles.append(f)
        else:
            hardFiles.append(f)
    if config.verbose:
        print '  making object rules (%i of %i hard)' % \
                  (len(hardFiles), len(hardFiles)+len(easyFiles))
    
    # there's only one rule for this object file, therefore we don't care
    # about its condition, if any:
    for f in easyFiles:
        src, cond = files[f][0]
        addRule(f, f, src, None)

    # these files are compiled from multiple sources, so we must create
    # conditional compilation rules:
    for f in hardFiles:
        srcfiles = containers.OrderedDict()
        for x in files[f]:
            src, cond = x
            if src not in srcfiles:
                srcfiles[src] = [cond]
            else:
                srcfiles[src].append(cond)
        i = 1
        for s in srcfiles:
            conds = srcfiles[s]
            if len(conds) > 1:
                changes = 0
                #print s, len(conds)
                #print [ x.name for x in conds ]
                lng = len(conds)
                for c1 in range(0,lng):
                    for c2 in range(c1+1,lng):
                        if conds[c1] == None: continue
                        #print conds[c1].name, conds[c2].name
                        r = reduceConditions(conds[c1], conds[c2])
                        #print 'reduction:',r
                        if r != None:
                            conds[c1] = 0
                            if r == '1':
                                conds[c2] = None
                            else:
                                conds[c2] = r
                            changes = 1
                            break
                #if changes:
                #    for c in [ x for x in conds if x != 0 ]:
                #        if c == None:
                #            print 'no cond'
                #        else:
                #            print 'cond: ',c.name
            for cond in conds:
                if cond == 0: continue
                addRule('%s%i' % (f,i), f, s, cond)
                i += 1
            

    return retval


def __certainlyNotEmpty(value):
    """Returns True if the given expression can be determined to be non-empty.
       Returns False if it is either empty or we don't know for sure.
       Input is non-empty, with surrounding whitespace already stripped."""

    if value[0] != '$': # the simple case
        return True

    class __Helper: pass
    helper = __Helper()
    helper.ok = False

    def varCb(helper, expr, use_options, target, add_dict):
        if not helper.ok: # don't waste time otherwise
            if expr in mk.options:
                if mk.options[expr].isNeverEmpty():
                    helper.ok = True
            # FIXME: it would be nice to be able to do this for condvars too,
            #        but they default to empty value if the set of its
            #        conditions is not exhaustive and so checking all items
            #        of its 'values' members is not enough, we'd have to verify
        return ''

    def textCb(helper, txt):
        if len(txt) > 0:
            helper.ok = True
        return ''

    mk.__doEvalExpr(value, varCb, textCb,
                    helper, # extra argument passed to callbacks
                    1,    # use_options
                    None, # target
                    None) # add_dict
    return helper.ok


def formatIfNotEmpty(fmt, value):
    """Return fmt % value (prefix: e.g. "%s"), unless value is empty string
       (in which case it returns empty string).
       Can handle following forms of 'value':
           - empty string
           - anything beginning with literal
           - anything with a literal in it
           - $(cv) where cv is conditional variable
    """

    if fmt == '': return ''
    value = value.strip()
    if value == '' or value.isspace():
        return ''

    if __certainlyNotEmpty(value):
        return fmt % value
    
    if value.startswith('$(') and value[-1] == ')':
        # FIXME: this is too limited, it should be done inside __doEvalExpr
        #        callbacks instead.
        condname = value[2:-1]
        if condname in mk.options:
            if mk.options[condname].isNeverEmpty():
                return fmt % value
            else:
                raise errors.Error("formatIfNotEmpty failed: option '%s' may be empty" % condname)

        if condname in mk.cond_vars:
            cond = mk.cond_vars[condname]
            var = mk.CondVar(makeUniqueCondVarName('%s_p' % cond.name))
            mk.addCondVar(var)
            for v in cond.values:
                var.add(v.cond, formatIfNotEmpty(fmt, v.value))
            return '$(%s)' % var.name

        if condname in mk.make_vars:
            form = formatIfNotEmpty(fmt, mk.make_vars[condname])
            if form == '': return ''
            return fmt % value

        if condname in mk.vars:
            form = formatIfNotEmpty(fmt, mk.vars[condname])
            if form == '': return ''
            return fmt % value
            
    raise errors.Error("formatIfNotEmpty failed: '%s' too complicated" % value)

def addPrefixIfNotEmpty(prefix, value):
    """Prefixes value with prefix, unless value is empty. 
       See formatIfNotEmpty for more details."""
    return formatIfNotEmpty(prefix+'%s', value)
    

def addPrefixToList(prefix, value):
    """Adds prefix to every item in 'value' interpreted as
       whitespace-separated list."""
    
    def callback(prefix, cond, sources):
        prf = suf = ''
        if sources[0].isspace(): prf=' '
        if sources[-1].isspace(): suf=' '
        retval = []
        for s in sources.split():
            retval.append(prefix+s)
        return '%s%s%s' % (prf, ' '.join(retval), suf)
    return substitute2(value, lambda c,s: callback(prefix,c,s))


def mkPathPrefix(p):
    if p == '.':
        return ''
    else:
        return p + '$(DIRSEP)'

def pathPrefixToPath(p):
    if p == '': return '.'
    else:       return p


CONDSTR_UNIXTEST = 'unixtest' # syntax of 'test' program
CONDSTR_MSVC     = 'msvc'     # C++-like syntax used by Borland and VC++ make
def condition2string(cond, format):
    """Converts condition to string expression in given format. This is useful
       for Empy templates that need to output condition strings."""
    if cond == None:
        return ''
    if format == CONDSTR_MSVC:
        return' && '.join(['"$(%s)" == "%s"' % (x.option.name,x.value) \
                           for x in cond.exprs])
    if format == CONDSTR_UNIXTEST:
        return ' -a '.join(['"x$%s" = "x%s"' % (x.option.name,x.value) \
                           for x in cond.exprs])
    raise errors.Error('unknown format')
                

def createMakeVar(target, var, makevar, hints=''):
    """Creates make variable called 'makevar' with same value as 'var' and
       returns reference to it in the form of $(makevar)."""
    tg = mk.targets[target]
    mk.setVar('%s_%s' % (safeMakefileValue(target.upper()), makevar),
              "$(ref('%s','%s'))" % (var, target),
              target=tg, makevar=1, hints=hints)
    return '$(%s_%s)' % (safeMakefileValue(target.upper()), makevar)


def wrapLongLine(prefix, line,
                 continuation, indent='\t', maxChars=None, variable=None):
    """Wraps the line so that it does not exceed 'maxChars' characters (if not
       specified, the default is used).  'continuation' is string appended to
       the end of unfinished line that continues on the next line. 'indent' is
       the string inserted before new line. The line is broken only at
       whitespaces.  It also discards whitespaces and replaces them with single
       ' '.  'variable' is a hint telling the function what variable's content
       is it processing (if any). If the variable has "files" hint set, then
       only one entry per line is written
    """
    if variable != None and variable in mk.vars_hints and \
                            'files' in mk.vars_hints[variable]:
        s = prefix
        for w in line.split():
            s += '%s\n%s%s' % (continuation, indent, w)
        return s

    if maxChars == None: # "use the default"
        maxChars = config.wrap_lines_at
    wrapDisabled = (maxChars == None)
    
    line = prefix+line
    if len(line) <= maxChars or wrapDisabled:
        return line.replace('\n', '%s\n%s' % (continuation, indent))
    
    always_len = len(continuation) + len(indent)
    splitted = line.split()
    s = splitted[0]
    lng = len(s) + len(indent)
    for w in splitted[1:]:
        wlen = len(w)
        if lng + wlen > maxChars:
            s += '%s\n%s%s' % (continuation, indent, w)
            lng = always_len + wlen
        else:
            s = '%s %s' % (s, w)
            lng += wlen
    return s


def safeSplit(str):
    """
       Splits the given string like the built-in split() python function but, unlike
       the python split() function, recognizes that an expression like:
                            "$(myPythonFuncCall(arg1, arg2)) item2"
       must be split as:
                        [ "$(myPythonFuncCall(arg1, arg2))", "item2" ]
       and not as the built-in split() function would do:
                      [ "$(myPythonFuncCall(arg1,", "arg2))", "item2" ]
    """
    # to make simpler our algorithm below we add a whitespace at the end:
    str = str.strip() + " "
    lst = []

    # scan  char by char the string
    bracketNestLevel = 0
    alreadyParsed = 0
    for i in range(len(str)):
        c = str[i]
        if c in string.whitespace and bracketNestLevel == 0:
            # discard empty tokens:
            token = str[alreadyParsed:i].strip()
            if token != '':
                # this whitespace is not enclosed by brackets; we can break
                # here:
                lst.append(token)
                # +1 is to remove the whitespace from next token:
                alreadyParsed = i + 1
        elif c == '(':
            bracketNestLevel += 1
        elif c == ')':
            bracketNestLevel -= 1
    return lst

def getOutputFileAbsPath():
    """ Returns the absolute path of the output file using the os.sep
        for currently-running OS """
    outputFile = mk.evalExpr(config.output_file, use_options=0)
    finalmakefile = os.path.abspath(
                os.path.split(currentosPaths(outputFile))[0])
    return finalmakefile

def getSrcDirAbsPath():
    """ Returns the output file's absolute path concatenated with SRCDIR
        using the os.sep for currently-running OS """
    finalmakefile = getOutputFileAbsPath()

    # convert SRCDIR_RAW to the path separator for the currently running OS:
    srcdir = currentosPaths(mk.vars['SRCDIR_RAW'])
    return os.path.join(finalmakefile, srcdir)

def fileList(pathlist):
    """
       Returns a string containing a space-separed list of all files
       found in the given path. 'path' typically is a relative path
       (absolute paths should be avoided in well-designed bakefiles)
       with a mask used to match only wanted files.
       When the given path is relative, it must be relative to SRCDIR
       global variable; remember that SRCDIR is in turn relative to
       the location of the generated makefile.

       Additionally this function can accept python lists of strings, too.
       The returned value is the list of all files found in all the paths
       of the list.

       E.g.
            <sources>$(fileList('../src/*.cpp'))</sources>
            <sources>$(fileList(['../src/*.cpp', '../src/*.c']))</sources>
    """
    def __fileList(path):
        # convert all vars to the path separator for the currently running OS:
        srcdir = getSrcDirAbsPath()
        path = currentosPaths(path)

        # the absolute path where we need to search files:
        p = os.path.join(srcdir, path)

        # NB: do not normalize the path since this could interfere with the
        #     prefix detection & removal later...
        prefix = srcdir + os.sep
        if p.startswith(prefix):
            srcdirPrefix = len(prefix)
        else:
            srcdirPrefix = 0

        files = glob.glob(p)
        dependencies.addDependencyWildcard(mk.vars['INPUT_FILE'],
                                           config.format,
                                           p)

        # remove prefix, normalize the filepath and use / for separator:
        files = [os.path.normpath(f[srcdirPrefix:]).replace(os.sep, '/')
                 for f in files]
                 
        # sort the files so that fileList() always give the same
        # orderered list for a given set of files regardless of the OS
        # (and of the specific glob() implementation) where it's running under
        files.sort()

        if config.debug:
            print "fileList('%s'): matches for '%s' pattern found: '%s'" % \
                  (path, os.path.normpath(p), ' '.join(files))

        return ' '.join(files)

    if isinstance(pathlist, str):
        return __fileList(pathlist)
    elif isinstance(pathlist, list):
        ret = ' '.join([__fileList(path) for path in pathlist])
        if config.debug:
            print "fileList(%s): returned '%s'" % (pathlist, ret.strip())
        return ret
    else:
        raise errors.Error('fileList() function only accepts a string or a python list of strings as argument')
        
def removeDuplicates(list):
    """
        Returns a copy of the given (space-separed) list with all 
        duplicate tokens removed.
    """
    retlist = set(list.split())
    return ' '.join(retlist)

def getDirsFromList(filedirlist):
    """
        Returns a (space-separed) list of all directories in the given list.
        Note that this function does a check at bakefile-time to determine if the
        tokens of the given list, prefixed with the path of the generated makefile
        and with the SRCDIR variable contents, are directories or not.
        This mostly makes sense only for internal use of Bakefile.
    """
    def __isDir(path):
        dir = os.path.dirname(currentosPaths(path))
        if dir=='' or dir=='.':
            return None
    
        # get the absolute SRCDIR in a format suitable for the currently running OS
        srcdir = getSrcDirAbsPath()
        
        # all variables used here have the right path separator for currently running OS:
        tocheck = os.path.join(srcdir, dir)
        if os.path.isdir(tocheck):
            return dir
        return None
    
    ret = [ ]
    for path in filedirlist.split():
        d = __isDir(path)
        if d!=None:
            ret.append(d)
    return removeDuplicates(' '.join(ret))

def dirName(path):
    """ Like os.path.dirname but uses DIRSEP and not os.sep """
    sep = mk.vars['DIRSEP']
    path = os.path.dirname(path.replace(sep, os.sep))
    return path.replace(os.sep, sep)
    
def joinPaths(path1, path2, path3='', path4=''):
    """ Mostly like os.path.join but uses DIRSEP and not os.sep """
    
    def _realjoin(path1, path2):
        sep = mk.vars['DIRSEP']
        if path1[-2:-1]!=sep:
            return path1 + sep + path2
        return path1 + path2

    return _realjoin(_realjoin(_realjoin(path1, path2), path3), path4)

def normPath(path):
    """ Like os.path.normpath but uses DIRSEP and not os.sep """
    sep = mk.vars['DIRSEP']
    path = os.path.normpath(path.replace(sep, os.sep))
    return path.replace(os.sep, sep)
