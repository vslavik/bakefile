
import mk, errors
import os


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
        if target==None:
            return "$(ref('%s'))" % var
        else:
            return "$(ref('%s', '%s'))" % (var,target)


def makeUniqueCondVarName(name):
    """Creates name for cond. var."""
    n = nb = '__%s' % (name.replace('-','_'))
    i = 1
    while n in mk.cond_vars:
        n = '%s_%i' % (nb, i)
        i += 1
    return n


substVarNameCounter = 0

def substitute(str, callback, desc=None):
    """Calls callback to substitute text in str by something else. Works with
       conditional variables, too."""

    if desc == None:
        global substVarNameCounter
        desc = '%i' % substVarNameCounter
        substVarNameCounter += 1
    
    def callbackVar(expr, use_options, target, add_dict):
        if expr not in mk.cond_vars:
            raise errors.Error("'%s' can't be used in this context, "%expr +
                               "not a conditional variable")
        cond = mk.cond_vars[expr]
        var = mk.CondVar(makeUniqueCondVarName('%s_%s' % (cond.name, desc)))
        mk.addCondVar(var)
        for v in cond.values:
            if '$' in v.value:
                var.add(v.cond, substitute(v.value, callback, desc))
            else:
                if len(v.value) == 0 or v.value.isspace():
                    var.add(v.cond, v.value)
                else:
                    var.add(v.cond, callback(v.value))
        return '$(%s)' % var.name

    def callbackTxt(expr):
        if len(expr) == 0 or expr.isspace(): return expr
        return callback(expr)
    
    return mk.__doEvalExpr(str, callbackVar, callbackTxt)


def substituteFromDict(str, dict, desc=None):
    """Like substitute(), but less generic: instead of calling callback, the
       text is looked up in a dictionary. This imposes the restriction that
       'str' may be only single word."""
    try:
        return substitute(str, lambda x: dict[x], desc)
    except KeyError:
        raise errors.Error('Invalid value')


def nativePaths(filenames):
    """Translates filenames from Unix to native filenames."""
    if mk.vars['TOOLSET'] == 'unix':
        return filenames
    else:
        return substitute(filenames,
                          lambda x: x.replace('/', mk.vars['DIRSEP']),
                          'FILENAMES')

def findSources(filenames):
    """Adds source filename prefix to files."""
    return substitute(filenames,
                      lambda x: '%s$(DIRSEP)%s' % (mk.vars['SRCDIR'], x),
                      'SOURCEFILES')


__src2obj = {}

def sources2objects(sources, target, ext, objSuffix=''):
    """Adds rules to compile object files from source files listed in
       'sources', when compiling target 'target', with object files extension
       being 'ext'. Optional 'objSuffix' argument is used to change the name
       of object file (e.g. to compile foo.c to foo_rc.o instead of foo.o).

       Returns object files list."""
    import os.path
    import reader, xmlparser

    # It's a bit faster (about 10% on wxWindows makefiles) to not parse XML
    # but construct the elements tree by hand. We construc the tree for this
    # code:
    #
    #code = """
    #<makefile>
    #<%s id="%s">
    #    <parent-target>%s</parent-target>
    #    <src>%s</src>
    #</%s>
    #</makefile>"""
    cRoot = xmlparser.Element()
    cTarget = xmlparser.Element()
    cSrc = xmlparser.Element()
    cParent = xmlparser.Element()
    cRoot.name = 'makefile'
    cRoot.children = [cTarget]
    cRoot.value = ''
    cTarget.children = [cParent,cSrc]
    cParent.name = 'parent-target'
    cTarget.value = ''
    cSrc.name = 'src'

    def callback(sources):
        prefix = suffix = ''
        if sources[0].isspace(): prefix=' '
        if sources[-1].isspace(): suffix=' '
        retval = []
        for s in sources.split():
            base, srcext = os.path.splitext(s)
            base = os.path.basename(base)
            objdir = mkPathPrefix(mk.vars['BUILDDIR'])
            index = (target,s,ext,objSuffix)
            if index not in __src2obj:
                obj = '%s%s%s%s' % (objdir, base, objSuffix, ext)
                if obj in mk.targets:
                    obj = '%s%s-%s%s%s' % (objdir, mk.targets[target].id, base,
                                           objSuffix, ext)
                    num=0
                    while obj in mk.targets:
                        num += 1
                        obj = '%s%s-%s%i%s%s' % (objdir, mk.targets[target].id,
                                                 base, num, objSuffix, ext)
                rule = '__%s-to-%s' % (srcext[1:], ext[1:])
                # 4 lines below are equivalent of:
                # code2 = code % (rule, obj, target, s, rule)
                cTarget.name = rule
                cTarget.props['id'] = obj
                cParent.value = target
                cSrc.value = s
                reader.processXML(cRoot)
                __src2obj[index] = obj
            retval.append(__src2obj[index])
        return '%s%s%s' % (prefix, ' '.join(retval), suffix)

    sources2 = nativePaths(sources)
    return substitute(sources2, callback, 'OBJECTS')


def formatIfNotEmpty(fmt, value):
    """Return fmt % value (prefix: e.g. "%s"), unless value is empty string.
       Can handle following forms of 'value':
           - empty string
           - anything beginning with literal
           - $(cv) where cv is conditional variable
    """

    if fmt == '': return ''
    value = value.strip()
    if value == '' or value.isspace():
        return ''
    if value[0] != '$':
        return fmt % value
    if value[-1] != ')' and not value[-1].isspace():
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
    raise errors.Error("formatIfNotEmpty failed: '%s' too complicated" % value)

def addPrefixIfNotEmpty(prefix, value):
    """Prefixes value with prefix, unless value is empty. 
       See formatIfNotEmpty for more details."""
    return formatIfNotEmpty(prefix+'%s', value)


def mkPathPrefix(p):
    if p == '.':
        return ''
    else:
        return p + '$(DIRSEP)'

