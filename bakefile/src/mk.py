
import utils, errors, config
from utils import *

vars = {}
override_vars = {}
options = {}
cond_vars = {}
targets = {}
templates = {}
conditions = {}

vars['targets'] = {}

class Option:
    def __init__(self, name, default, desc, values):
        self.name = name
        self.default = default
        self.desc = desc
        self.values = values


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
        pass
    def __init__(self, name, target=None):
        self.name = name
        self.values = []
        self.target = target
    def add(self, cond, value):
        v = CondVar.Value()
        v.cond = cond
        v.value = value
        self.values.append(v)

class Target:
    class Struct: pass
    def __init__(self, type, id, condition):
        self.cond = condition
        self.type = type
        self.id = id
        self.vars = {}
        self.vars['id'] = id
        self.vars['type'] = self.type
        xxx = Target.Struct()
        xxx.__dict__ = self.vars
        vars['targets'][id] = xxx


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

def addTarget(target):
    # add the target:
    targets[target.id] = target

def setVar(name, value, eval=1, target=None, add_dict=None, store_in=None,
           append=0, overwrite=1):
    if store_in != None: store = store_in
    elif target != None: store = target.vars
    else:                store = vars
    
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
    if append:
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
                if not evalExpr('$(%s)' % c, use_options=0):
                    return '0'
            except NameError: pass        
        return None

def makeCondition(cond_str):
    cond_list = __splitConjunction(cond_str)
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
        conditions[cname] = c
        return c

__curNamespace = {}

def __evalPyExpr(expr, use_options=1, target=None, add_dict=None):
    if use_options:
        vlist = [__vars_opt, vars]
    else:
        vlist = [vars]
    if target != None:
        vlist.append(target.vars)
    if add_dict != None:
        vlist.append(add_dict)

    for v in range(len(vlist)-1,-1,-1):
        if expr in vlist[v]:
            return vlist[v][expr]
   
    v = vlist[0].copy()
    for i in vlist[1:]: v.update(i)
    global __curNamespace
    oldNS = __curNamespace
    __curNamespace = v
    val = eval(expr, globals(), v)
    __curNamespace = oldNS
    return str(val)

def __doEvalExpr(e, varCallb, textCallb,
                 use_options=1, target=None, add_dict=None):
    if textCallb == None:
        textCallb = lambda x: x
    lng = len(e)
    i = 0
    txt = ''
    output = ''
    while i < lng-1:
        if e[i] == '$' and e[i+1] == '(' and (i == 0 or e[i-1] != '\\'):
            if txt != '':
                output += textCallb(txt)
            txt = ''
            code = ''
            i += 2
            braces = 1
            while i < lng:
                if e[i] == ')':
                    braces -= 1
                    if braces == 0:
                        output += varCallb(code, use_options, target, add_dict)
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
    output += textCallb(txt + e[i:])
    return output


def evalExpr(e, use_options=1, target=None, add_dict=None):    
    return __doEvalExpr(e, __evalPyExpr, None, use_options, target, add_dict)


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
