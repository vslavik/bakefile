
import string, sys, copy, os, os.path
import xmlparser
import mk
import utils
import errors
from errors import ReaderError
import config

def evalConstExpr(e, str, target=None):
    try:
        return mk.evalExpr(str, use_options=0, target=target)
    except NameError, err:
        raise ReaderError(e, "can't use options or conditional variables in this context (%s)" % err)


def evalWeakCondition(e):
    """Evaluates e's 'cond' property, if present, and returns 0 or 1 if it
       can be evaluated to a constant. If it can't (i.e. it is a strong
       condition) do it, raises exception."""
    if 'cond' not in e.props:
        return 1
    condstr = e.props['cond']
    typ = mk.evalCondition(condstr)
    # Condition never met when generating this target:
    if typ == '0':
        return 0
    # Condition always met:
    elif typ == '1':
        return 1
    else:
        raise ReaderError(e,
                "'%s': only weak condition allowed in this context" % condstr)


def handleSet(e, target=None, add_dict=None):
    errors.pushCtx(e)
    name = e.props['var']
    if (name in mk.override_vars) and target == None:
        errors.popCtx()
        return # can't change value of variable overriden with -D=xxx
    
    doEval = not ('eval' in e.props and e.props['eval'] == '0')
    overwrite = not ('overwrite' in e.props and e.props['overwrite'] == '0')
    isCond = (len(e.children) > 0)
    value = e.value

    # Handle conditions:
    if isCond:
        for e_if in e.children:
            if e_if.name != 'if':
                raise ReaderError(e_if, "malformed <set> command")
        
            # Preprocess always true or always false conditions:
            condstr = e_if.props['cond']
            if condstr == 'target':
                if target == None:
                    raise ReaderError(e_if, "'target' condition can't be used at global scope")
                cond = target.cond
                if cond == None:
                    isCond = 0
                    value = e_if.value
                    break
            else:
                typ = mk.evalCondition(condstr)
                # Condition never met when generating this target:
                if typ == '0':
                    continue
                # Condition always met:
                elif typ == '1':
                    isCond = 0
                    value = e_if.value
                    break
                elif typ != None:
                    raise ReaderError(e, "malformed condition: '%s'" % condstr)
                cond = mk.makeCondition(condstr)

            # Real conditions:
            if 'scope' in e.props:
                raise ReaderError(e, "conditional variable can't have nondefault scope ('%s')" % e.props['scope'])

            name = e.props['var']
            if target != None:
                if (not overwrite) and (name in target.vars):
                    errors.popCtx()
                    return
                name = '__%s_%s' % (target.id, name)
                mk.setVar(e.props['var'], '$(%s)' % name,
                             eval=0, target=target,
                             add_dict=add_dict)
            if cond == None:
                raise ReaderError(e, "malformed condition: '%s'" % condstr)
            if name in mk.cond_vars:
                if not overwrite:
                    errors.popCtx()
                    return
                var = mk.cond_vars[name]
            else:
                var = mk.CondVar(name, target)
                mk.addCondVar(var)
            if doEval:
                value = mk.evalExpr(e_if.value,target=target,add_dict=add_dict)
            else:
                value = e_if.value
            var.add(cond, value)
        if isCond: 
            errors.popCtx()
            return

    # Non-conditional variables:
    if value == None: value = ''
    if 'append' in e.props and e.props['append'] == '1':
        doAppend = 1
    else:
        doAppend = 0
    store_in = None
    if 'scope' in e.props:
        sc = evalConstExpr(e, e.props['scope'], target=target)
        if sc == 'local':
            pass
        elif sc == 'global':
            store_in = mk.vars
        else:
            if sc in mk.targets:
                store_in = mk.targets[sc].vars
            else:
                raise ReaderError(e, "invalid scope '%s': must be 'global', 'local' or target name" % sc)
    mk.setVar(name, value, eval=doEval, target=target,
              add_dict=add_dict, store_in=store_in,
              append=doAppend, overwrite=overwrite)
    errors.popCtx()


def handleUnset(e):
    name = e.props['var']
    if not mk.unsetVar(name):
        raise ReaderError(e, "'%s' is not a variable" % name)


def handleOption(e):
    name = e.props['name']
    if name in mk.options:
        raise ReaderError(e, "option '%s' already defined" % name)

    if name in mk.override_vars:
        return # user hardcoded the value with -D=xxx

    default = None
    desc = None
    values = None
    for c in e.children:
        if c.name == 'default-value':
            default = evalConstExpr(e, c.value)
        elif c.name == 'description':
            desc = c.value
        elif c.name == 'values':
            values = evalConstExpr(e, c.value).split()
    mk.addOption(mk.Option(name, default, desc, values))


def extractTemplates(e):
    ch = []
    if 'template' in e.props:
        derives = e.props['template'].split(',')
        for d in derives:
            try:
                ch2 = mk.templates[d]
                ch = ch + ch2
            except KeyError:
                raise ReaderError(e, "unknown template '%s'" % d)
    return ch

def applyTemplates(e, templ):
    if len(templ) == 0:
        return e
    e = copy.copy(e)
    e.children = templ + e.children
    return e


def handleTemplate(e):
    id = e.props['id']
    if id in mk.templates:
        raise ReaderError(e, "template ID '%s' already used" % id)
    mk.templates[id] = applyTemplates(e, extractTemplates(e)).children



rules = {}
class Rule:
    def __init__(self, name):
        self.name = name
        self.baserules = []
        self.tags = {}
        self.template = []

    def getTemplates(self):
        t = []
        for b in self.baserules:
            t = t + b.getTemplates()
        t = t + self.template
        return t

    def getTagsDict(self):
        d = {}
        for b in self.baserules:
            d2 = b.getTagsDict()
            for key in d2:
                if key in d: d[key] += d2[key]
                else: d[key] = copy.copy(d2[key])
        for key in self.tags:
            if key in d: d[key] += self.tags[key]
            else: d[key] = copy.copy(self.tags[key])
        return d

    

def handleModifyTarget(e, dict):
    tg = mk.evalExpr(e.props['target'], use_options=0, add_dict=dict)
    if tg not in mk.targets:
        raise ReaderError(e, "unknown target '%s'" % tg)
    target = mk.targets[tg]
    tags = rules[target.type].getTagsDict()
    _processTargetNodes(e.children, target, tags, dict)


def _processTargetNodes(list, target, tags, dict):
    def processCmd(e, target, dict):        
        if e.name == 'set':
            handleSet(e, target=target, add_dict=dict)
        elif e.name == 'modify-target':
            if dict != None:
                v = {}
                v.update(target.vars)
                v.update(dict)
                handleModifyTarget(e, v)
            else:
                handleModifyTarget(e, target.vars)
        elif e.name == 'add-target':
            e2 = copy.deepcopy(e)
            e2.props['id'] = mk.evalExpr(e2.props['target'],
                                         target=target, add_dict=dict)
            del e2.props['target']
            e2.name = e2.props['type']
            if 'cond' in e2.props and e2.props['cond'] == 'target':
                if target.cond == None:
                    del e2.props['cond']
                else:
                    e2.props['cond'] = target.cond.tostr()
            handleTarget(e2)
        else:
            return 0
        return 1
    
    for node in list:
        if not processCmd(node, target, dict):
            if node.name not in tags:
                raise ReaderError(node,
                                      "unknown target tag '%s'" % node.name)
            if evalWeakCondition(node) == 0:
                continue
            dict2 = {}
            dict2['value'] = mk.evalExpr(node.value,
                                         target=target, add_dict=dict)
            _processTargetNodes(tags[node.name], target, tags, dict2)


def handleTarget(e):
    if e.name not in rules:
        raise ReaderError(e, "unknown target type")

    cond = None
    if 'cond' in e.props:
        isCond = 1
        # Handle conditional targets:
        condstr = e.props['cond']
        typ = mk.evalCondition(condstr)
        # Condition never met, ignore the target:
        if typ == '0': return
        # Condition always met:
        elif typ == '1':
            isCond = 0
        elif typ != None:
            raise ReaderError(e, "malformed condition: '%s'" % condstr)

        if isCond:
            cond = mk.makeCondition(condstr)
            if cond == None:
                raise ReaderError(e, "malformed condition: '%s'" % condstr)
        
    rule = rules[e.name]
    tags = rule.getTagsDict()
    e = applyTemplates(e, rule.getTemplates() + extractTemplates(e))
    id = e.props['id']
    if id in mk.targets:
        raise ReaderError(e, "duplicate target name '%s'" % id)
    
    target = mk.Target(e.name, id, cond)
    mk.addTarget(target)

    errors.pushCtx("when processing target at %s" % e.location())
    _processTargetNodes(e.children, target, tags, None)
    errors.popCtx()


def handleDefineRule(e):
    rule = Rule(evalConstExpr(e, e.props['name']))
    rules[rule.name] = rule
    HANDLERS[rule.name] = handleTarget

    if 'extends' in e.props:
        baserules = [evalConstExpr(e,x) for x in e.props['extends'].split(',')]
        rule.baserules = []
        for baserule in baserules:
            if baserule not in rules:
                raise ReaderError(e, "unknown rule '%s'" % baserule)
            rule.baserules.append(rules[baserule])

    for node in e.children:
        if node.name == 'define-tag':
            handleDefineTag(node, rule=rule)
        elif node.name == 'template':
            rule.template += applyTemplates(node,
                                            extractTemplates(node)).children
        else:
            raise ReaderError(node,
                       "unknown element '%s' in <define-rule>" % node.name)


def handleDefineTag(e, rule=None):
    name = e.props['name']
    if rule == None:
        if 'rules' in e.props:
            rs = e.props['rules'].split(',')
        else:
            raise ReaderError(e, "external <define-tag> must list rules")
    else:
        rs = [rule.name]
    
    for rn in rs:
        if not rn in rules:
            raise ReaderError(e, "unknown rule '%s'" % rn)
        r = rules[rn]
        if name in r.tags:
            r.tags[name] += e.children
        else:
            r.tags[name] = copy.copy(e.children)

loadedModules = []
availableFiles = []

def buildModulesList():
    class ModuleInfo: pass
    def visit(basedir, dirname, names):
        dir = dirname[len(basedir)+1:]
        if dir != '':
            dircomp = dir.split(os.sep)
        else:
            dircomp = []
        for n in names:
            ext =os.path.splitext(n)[1]
            if ext != '.bakefile' and ext != '.bkl': continue
            i = ModuleInfo()
            i.file = os.path.join(dirname,n)
            i.modules = dircomp + os.path.splitext(n)[0].split('-')
            availableFiles.append(i)

    for p in config.searchPath:
        os.path.walk(p, visit, p)


def loadModule(m):
    if m in loadedModules:
        return
    if config.verbose: print "loading module '%s'..." % m
    loadedModules.append(m)
    
    # set USING_<MODULENAME> variable:
    mk.setVar('USING_%s' % m.upper(), '1')
    
    # import module's py utilities:
    mk.importPyModule(m)
    
    # include module-specific makefiles:
    global availableFiles
    for f in availableFiles:
        if m in f.modules:
            f.modules.remove(m)
            if len(f.modules) == 0:
                processFile(f.file)
    availableFiles = [f for f in availableFiles if len(f.modules)>0]


def handleUsing(e):
    modules = e.props['module'].split(',')
    for m in modules:
        loadModule(m)


def handleInclude(e):
    file = evalConstExpr(e, e.props['file'])
    canIgnore = 'ignore_missing' in e.props and e.props['ignore_missing'] == '1'
    lookup = [os.path.dirname(e.filename)] + config.searchPath
    errors.pushCtx("included from %s" % e.location())
    for dir in lookup:
        if processFileIfExists(os.path.join(dir, file)):
            errors.popCtx()
            return
    if not canIgnore:
        raise ReaderError(e, "can't find file '%s' in %s" % (file,
                              string.join(lookup, ':')))
    errors.popCtx()


def handleOutput(e):
    file = mk.evalExpr(e.props['file'], use_options=0)
    writer = mk.evalExpr(e.props['writer'], use_options=0)
    if 'method' in e.props:
        method = mk.evalExpr(e.props['method'], use_options=0)
    else:
        method = 'replace'
    config.to_output.append((file, writer, method))
    


HANDLERS = {
    'set':           handleSet,
    'unset':         handleUnset,
    'option':        handleOption,
    'using':         handleUsing,
    'template':      handleTemplate,
    'include':       handleInclude,
    'define-rule':   handleDefineRule,
    'define-tag':    handleDefineTag,
    'output':        handleOutput,
    }


def __doProcess(file=None, strdata=None):
    # FIXME: validity checking
    try:
        if file != None:
            m = xmlparser.parseFile(file)
        else:
            m = xmlparser.parseString(strdata)
    except xmlparser.ParsingError:
        raise ReaderError(None, "file '%s' is invalid" % file)

    def processNodes(list):
        for e in list:
            if e.name == 'if':
                if evalWeakCondition(e):
                    processNodes(e.children)
            else:
                try:
                    h=HANDLERS[e.name]
                except(KeyError):
                    raise ReaderError(e, "unknown tag '%s'" % e.name)
                h(e)
    
    try:
        processNodes(m.children)
    except ReaderError, ex:
        raise ex
    # FIXME: enable this code when finished programming:
    #except Exception, ex:
    #    raise ReaderError(e, ex)

def processFile(filename):
    if not os.path.isfile(filename):
        raise ReaderError(None, "file '%s' doesn't exist" % filename)
    if config.verbose:
        print 'loading %s...' % filename
    sys.path.append(os.path.dirname(os.path.abspath(filename)))
    __doProcess(file=filename)

def processFileIfExists(filename):
    if os.path.isfile(filename):
        processFile(filename)
        return 1
    else:
        return 0

def processString(data):
    __doProcess(strdata=data)

from types import InstanceType, DictType

def finalEvaluation():
    """Evaluates all variables, so that unneccessary $(...) parts are
       removed in cases when <set eval="0" ...> was used"""

    # Replace $(foo) for options by config.variableSyntax format:
    for v in mk.__vars_opt:
        mk.__vars_opt[v] = config.variableSyntax % v

    def iterateModifications():
        class Modified: pass
        modified = Modified()
        modified.v = 1
        def modify(old, new, m):
            if old != new: m.v += 1
            return new

        while modified.v:
            if config.verbose:
                sys.stdout.write('.')
                sys.stdout.flush()
            modified.v = 0
            for v in mk.vars:
                if not (type(mk.vars[v]) is InstanceType or
                        type(mk.vars[v]) is DictType):
                    if '$' in mk.vars[v]:
                        mk.vars[v] = modify(mk.vars[v], mk.evalExpr(mk.vars[v]),
                                            modified)
            for t in mk.targets.values():
                for v in t.vars:
                    if not (type(t.vars[v]) is InstanceType or 
                            type(t.vars[v]) is DictType):
                        try:
                            if '$' in t.vars[v]:
                                t.vars[v] = modify(t.vars[v],
                                                   mk.evalExpr(t.vars[v],
                                                               target=t),
                                                   modified)
                        except KeyError, err:
                            raise ReaderError(None, "can't evaluate value '%s' of variable '%s' on target '%s'" % (t.vars[v], v, t.id))
            for c in mk.cond_vars.values():
                for v in c.values:
                    if '$' in v.value:
                        v.value = modify(v.value,
                                         mk.evalExpr(v.value, target=c.target),
                                         modified)
    
    if config.verbose:
        sys.stdout.write('finalizing ')
    iterateModifications()
    utils.__refEval = 1
    iterateModifications()

    # Replace all occurences of \$ by $:
    for v in mk.vars:
        if not (type(mk.vars[v]) is InstanceType or
                type(mk.vars[v]) is DictType):
            mk.vars[v] = mk.vars[v].replace('\\$', '$')
    for t in mk.targets.values():
        for v in t.vars:
            if not (type(t.vars[v]) is InstanceType or
                    type(t.vars[v]) is DictType):
                t.vars[v] = t.vars[v].replace('\\$', '$')
    for o in mk.options.values():
        if o.default == None: continue
        o.default = o.default.replace('\\$', '$')
    for c in mk.cond_vars.values():
        for v in c.values:
            v.value = v.value.replace('\\$', '$')
    
    if config.verbose: sys.stdout.write('\n')




# -------------------------------------------------------------------------

def setStdVars():
    mk.setVar('LF', '\n')
    mk.setVar('OUTPUT_FILE', config.output_file)
    mk.setVar('FORMAT', config.format)

def setOverrideVars():
    for v in config.defines:
        mk.setVar(v, config.defines[v])
        mk.override_vars[v] = config.defines[v]
    

def read(filename):
    try:
        setStdVars()
        setOverrideVars()
        buildModulesList()
        loadModule('common')
        loadModule(config.format)
        processFile(filename)
        finalEvaluation()
        return 1
    except errors.ErrorBase, e:
        sys.stderr.write(str(e))
        return 0
