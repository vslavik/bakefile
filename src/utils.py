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
#  Misc utility functions for use in Bakefiles
#

import mk, errors, config, sys, os
import containers

def checkBakefileVersion(version):
    """Returns true iff current bakefile version is at least 'version'.
       'version' is string with three numbers separated with dots,
       e.g. '0.1.4'."""
    vcur = mk.vars['BAKEFILE_VERSION'].split('.')
    vreq = version.split('.')
    return vcur >= vreq

def isoption(name):
    return name in mk.__vars_opt

def isdefined(name):
    try:
        exec('__foo__ = %s' % name, mk.__curNamespace)
    except NameError:
        return isoption(name)
    return 1


def ifthenelse(cond, iftrue, iffalse):
    if eval(str(cond)): return iftrue
    else: return iffalse


__refEval = 0
def ref(var, target=None):
    if __refEval:
        if target==None or var not in mk.targets[target].vars:
            return mk.vars[var]
        else:
            return mk.targets[target].vars[var]
    else:
        if mk.__trackUsage: mk.__usageTracker.refs += 1
        if target==None:
            return "$(ref('%s'))" % var
        else:
            return "$(ref('%s', '%s'))" % (var,target)

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
    try:
        return substitute(str, lambda x: dict[x], desc)
    except KeyError:
        raise errors.Error("Invalid value '%s'" % str)


def nativePaths(filenames):
    """Translates filenames from Unix to native filenames."""
    if mk.vars['TOOLSET'] == 'unix':
        return filenames
    else:
        return substitute(filenames,
                          lambda x: x.replace('/', mk.vars['DIRSEP']),
                          'FILENAMES',
                          caller='nativePaths')

def findSources(filenames):
    """Adds source filename prefix to files."""
    return substitute(filenames,
                      lambda x: '%s%s%s' % \
                             (mk.vars['SRCDIR'], mk.vars['DIRSEP'], x),
                      'SOURCEFILES')


def getObjectName(source, target, ext, objSuffix=''):
    pos = source.rfind('.')
    srcext = source[pos:]
    base = source[:pos]
    pos = max(base.rfind('/'), base.rfind(mk.vars['DIRSEP']))
    base = base[pos+1:]
    
    objdir = mkPathPrefix(mk.vars['BUILDDIR'])
    objname = '%s%s_%s%s%s' % (objdir, mk.targets[target].id, base,
                               objSuffix, ext)
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

    def callback(cond, sources):
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
                    all[e.option] = 1
                elif e.value != all[e.option].value and \
                     e.option.values != None and len(e.option.values) == 2:
                    all[e.option] = 0
                else:
                    return None
            else:
                return None
        ret = []
        for e in all:
            if all[e] == 0:
                pass
            elif all[e] == 1:
                ret.append("%s=='%s'" % (e.name, values[e]))
            else:
                return None                
        if len(ret) == 0:
            return '1'
        else:
            return mk.makeCondition(' and '.join(ret))
 
    sources2 = nativePaths(sources)
    retval = substitute2(sources2, callback, 'OBJECTS', hints='files')

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


class __CounterHelper: pass
def __containsLiteral(expr):
    counter = __CounterHelper()
    counter.c = 0
    def textCb(counter, txt):
        if len(txt) > 0: counter.c = 1
        return ''
    mk.__doEvalExpr(expr, lambda a,b,c,d,e: '', textCb, counter,
                           1,    # use_options
                           None, # target
                           None) # add_dict
    return counter.c > 0

def formatIfNotEmpty(fmt, value):
    """Return fmt % value (prefix: e.g. "%s"), unless value is empty string
       (in which case it returns empty string).
       Can handle following forms of 'value':
           - empty string
           - anything beginning with literal
           - anything with a literal in it
           - $(cv) where cv is conditional variable
    """

    def __isNotEmpty(value):
        return ((value[0] != '$') or
                (value[-1] != ')' and not value[-1].isspace()) or
                __containsLiteral(value))

    if fmt == '': return ''
    value = value.strip()
    if value == '' or value.isspace():
        return ''
    if __isNotEmpty(value):
        return fmt % value
    
    if value.startswith('$(') and value[-1] == ')':
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
    mk.setVar('%s_%s' % (target.upper(), makevar),
              "$(ref('%s','%s'))" % (var, target),
              target=tg, makevar=1, hints=hints)
    return '$(%s_%s)' % (target.upper(), makevar)


def wrapLongLine(prefix, line,
                 continuation, indent='\t', maxChars=75, variable=None):
    """Wraps the line so that it does not exceed 'maxChars' characters.
       'continuation' is string appended to the end of unfinished line
       that continues on the next line. 'indent' is the string inserted
       before new line. The line is broken only at whitespaces.
       It also discards whitespaces and replaces them with single ' '.
       'variable' is a hint telling the function what variable's content is it
       processing (if any). If the variable has "files" hint set, then only
       one entry per line is written
    """
    if variable != None and variable in mk.vars_hints and \
                            'files' in mk.vars_hints[variable]:
        s = prefix
        for w in line.split():
            s += '%s\n%s%s' % (continuation, indent, w)
        return s
        
    line = prefix+line
    if len(line) <= maxChars:
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

