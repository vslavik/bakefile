#
# Makefile variables, conditions etc. and evaluation code are located here
#
# $Id$
#

import utils, errors, config
from utils import *

vars = {}
override_vars = {}
options = {}
cond_vars = {}
make_vars = {}
targets = {}
templates = {}
conditions = {}
fragments = []

vars['targets'] = {}

class Option:
    def __init__(self, name, default, desc, values):
        self.name = name
        self.default = default
        self.desc = desc
        self.values = values
        self.neverEmpty = 0

    def isNeverEmpty(self):
        if self.neverEmpty: return 1
        if len(self.values) > 0:
            for v in self.values:
                if len(v.strip()) == 0: return 0
            return 1
        return 0


class Condition:
    class Expr:
        def __init__(self, option, value):
            self.option = option
            self.value = value
        
    def __init__(self, name, exprs):
        self.name = name
        self.exprs = exprs
                    
    def tostr(self):
        parts = [ "%s=='%s'" % (x.option.name,x.value) for x in self.exprs ]
        return ' and '.join(parts)

class CondVar:
    class Value:
        def __cmp__(self, other):
            if self.cond.name < other.cond.name: return -1
            if self.cond.name == other.cond.name: return 0
            return 1

    def __init__(self, name, target=None):
        self.name = name
        self.values = []
        self.__sorted = 1
        self.target = target

    def add(self, cond, value):
        v = CondVar.Value()
        v.cond = cond
        v.value = value
        self.values.append(v)
        self.__sorted = 0

    def equals(self, other):
        # NB: can only be called _after_ finalize.finalEvaluation, i.e. when
        #     self.target is no longer meaningful
        if len(self.values) != len(other.values):
            return 0
        if not self.__sorted:
            self.values.sort()
            self.__sorted = 1
        if not other.__sorted:
            other.values.sort()
            other.__sorted = 1
        for i in range(0,len(self.values)):
            if self.values[i].cond != other.values[i].cond or \
               self.values[i].value != other.values[i].value:
                return 0
        return 1

class Target:
    class Struct: pass
    def __init__(self, type, id, condition, pseudo):
        self.cond = condition
        self.type = type
        self.id = id
        self.pseudo = pseudo
        self.vars = {}
        self.vars['id'] = id
        self.vars['type'] = self.type
        xxx = Target.Struct()
        xxx.__dict__ = self.vars
        vars['targets'][id] = xxx


class Fragment:
    """Part of native makefile copied as-is into generated output."""
    def __init__(self, content):
        self.content = content


# Like mk.vars, but for mk.options (i.e. not "real" variables). It's only
# purpose is to make Python code evaluation easier:
__vars_opt = {}

def addOption(opt):
    options[opt.name] = opt
    __vars_opt[opt.name] = '$(%s)' % opt.name

def addCondition(cond):
    conditions[cond.name] = cond

def addCondVar(cv):
    cond_vars[cv.name] = cv
    __vars_opt[cv.name] = '$(%s)' % cv.name

def addMakeVar(var, value):
    make_vars[var] = value
    vars[var] = '$(%s)' % var

def addTarget(target):
    # add the target:
    targets[target.id] = target

def addFragment(fragment):
    fragments.append(fragment)

def setVar(name, value, eval=1, target=None, add_dict=None, store_in=None,
           append=0, overwrite=1, makevar=0):
    if store_in != None: store = store_in
    elif target != None: store = target.vars
    else:                store = vars

    if makevar and vars['FORMAT_HAS_VARIABLES'] != '1':
        return
    
    if (name in override_vars) and (store == vars):
        return # values of user-overriden variables can't be changed

    if not overwrite:
        if name in store:
            return
        if store == vars and (name in options) or (name in cond_vars):
            return
    
    if eval:
        try:
            v = evalExpr(value, target=target, add_dict=add_dict)
        except Exception,e:
            raise errors.Error("failed to set variable: %s" % e)
    else:
        v = value
    if makevar:
        addMakeVar(name, v)
    else:
        if append and name in store:
            store[name] = '%s %s' % (store[name], v)
        else:
            store[name] = v

def unsetVar(name):
    if name in vars:
        del vars[name]
        return 1
    elif name in cond_vars:
        del cond_vars[name]
        del __vars_opt[name]
        return 1
    return 0
            
def setTargetVars(target, src):
    v = src.vars.copy()
    v.update(target.vars)
    target.vars = v
    
def __splitConjunction(expr):
    pos = expr.find(' and ')
    if pos == -1:
        return [expr]
    else:
        return [expr[:pos]] + __splitConjunction(expr[pos+5:])

def evalCondition(cond):
    try:
        return evalExpr('$(%s)' % cond, use_options=0)
    except NameError:
        # it may be a "() and () and ()" statement with some part = 0:
        for c in __splitConjunction(cond):
            try:
                if evalExpr('$(%s)' % c, use_options=0) == '0':
                    return '0'
            except NameError: pass
        return None

def makeCondition(cond_str):
    cond_list = __splitConjunction(cond_str)
    cond_list.sort()
    condexpr_list = []
    for cond in cond_list:
        if evalCondition(cond) == '1': continue
        pos = cond.find('==')
        if pos == -1:
            return None
        name = cond[:pos]
        value = cond[pos+2:]
        if value[0] == value[-1] and value[0] in ['"',"'"]:
            value = value[1:-1]
        else:
            try:
                value = int(value)
            except ValueError:
                return None
        condexpr_list.append(Condition.Expr(options[name], value))

    cname = '_'.join(['%s_%s' % (e.option.name.upper(),
                                 str(e.value).upper()) for \
                      e in condexpr_list])
    if cname in conditions:
        return conditions[cname]
    else:
        c = Condition(cname, condexpr_list)
        addCondition(c)
        return c

def mergeConditions(cond1, cond2):
    if cond1 == None or len(cond1.exprs) == 0: return cond2
    if cond2 == None or len(cond2.exprs) == 0: return cond1

    parts1 = [ "%s=='%s'" % (x.option.name,x.value) for x in cond1.exprs ]
    parts2 = [ "%s=='%s'" % (x.option.name,x.value) for x in cond2.exprs ]
    for p in parts2:
        if p not in parts1:
            parts1.append(p)
    
    return makeCondition(' and '.join(parts1))


# this is hack to get some information from __doEvalExpr for use in
# finalize.py where we want to know that some variable only depends on
# options and condvars and is thus not worth further evaluation:
class UsageTracker: pass
__trackUsage = 0
__usageTracker = UsageTracker()
def __resetUsageTracker(reset_coverage):
    global __usageTracker
    __usageTracker.vars = 0               # ordinary variables (inc.target ones)
    __usageTracker.optionsAndCondVars = 0 # options & conditional vars
    __usageTracker.makevars = 0           # make variables
    __usageTracker.pyexprs = 0            # other python expressions
    __usageTracker.refs = 0               # utils.ref() calls
    if reset_coverage:
        __usageTracker.map = {}           # 1 for every option, makevar or
                                          # condvar used

__curNamespace = {}

def __evalPyExpr(nothing, expr, use_options=1, target=None, add_dict=None):
    if use_options:
        vlist = [__vars_opt, vars]
    else:
        vlist = [vars]
    if target != None:
        vlist.append(target.vars)
    if add_dict != None:
        vlist.append(add_dict)

    for v in range(len(vlist)-1,-1,-1):
        d = vlist[v]
        if expr in d:
            if __trackUsage:
                if d is __vars_opt:
                    __usageTracker.optionsAndCondVars += 1
                    __usageTracker.map[expr] = 1
                elif d is vars and expr in make_vars:
                    __usageTracker.makevars += 1
                    __usageTracker.map[expr] = 1
                else:
                    __usageTracker.vars += 1
            return d[expr]
    
    if __trackUsage:
        __usageTracker.pyexprs += 1
   
    v = vlist[0].copy()
    for i in vlist[1:]: v.update(i)
    global __curNamespace
    oldNS = __curNamespace
    __curNamespace = v
    val = eval(expr.replace('\\','\\\\'), globals(), v)
    __curNamespace = oldNS
    return str(val)


def __doEvalExpr(e, varCallb, textCallb, moreArgs,
                 use_options=1, target=None, add_dict=None):
    if textCallb == None:
        textCallb = lambda y,x: x
    lng = len(e)
    i = 0
    txt = ''
    output = ''
    while i < lng-1:
        if e[i] == '$' and e[i+1] == '(' and (i == 0 or e[i-1] != '\\'):
            if txt != '':
                output += textCallb(moreArgs, txt)
            txt = ''
            code = ''
            i += 2
            braces = 1
            while i < lng:
                if e[i] == ')':
                    braces -= 1
                    if braces == 0:
                        output += varCallb(moreArgs,
                                           code, use_options, target, add_dict)
                        break
                    else:
                        code += e[i]
                elif e[i] == '(':
                    braces += 1
                    code += e[i]
                elif e[i] == "'" or e[i] == '"':
                    what = e[i]
                    code += e[i]
                    while i < lng:
                        i += 1
                        code += e[i]
                        if e[i] == what: break
                else:
                    code += e[i]
                i += 1
        else:
            txt += e[i]
        i += 1
    output += textCallb(moreArgs, txt + e[i:])
    return output


def evalExpr(e, use_options=1, target=None, add_dict=None):    
    return __doEvalExpr(e, __evalPyExpr, None,
                        moreArgs=None,
                        use_options=use_options, 
                        target=target, 
                        add_dict=add_dict)


def importPyModule(modname):
    try:
        exec('import utils.%s' % modname, globals())
        if config.verbose:
            print 'imported python module utils.%s' % modname
    except ImportError: pass

    try:
        exec('import %s' % modname, globals())
        if config.verbose:
            print 'imported python module %s' % modname
    except ImportError: pass
