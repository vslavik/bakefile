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
#  Makefile variables, conditions etc. and evaluation code are located here
#

import utils, errors, config, containers
import bottlenecks
from utils import *

vars = containers.OrderedDict()
override_vars = {}
options = containers.OrderedDict()
cond_vars = containers.OrderedDict()
make_vars = containers.OrderedDict()
# targets = {} ... declared below, needs Target class
templates = {}
conditions = containers.OrderedDict()
fragments = []
vars_hints = {}

vars['targets'] = {}

class Option:

    CATEGORY_UNSPECIFICED = 'unspecified'
    CATEGORY_PATH = 'path'

    def __init__(self, name, default, desc, values, values_desc):
        self.name = name
        self.default = default
        self.desc = desc
        self.values = values
        self.category = Option.CATEGORY_UNSPECIFICED
        self.values_desc = {}
        if self.values != None:
            if values_desc != None:
                for i in range(0,len(self.values)):
                    desc = values_desc[i]
                    if desc.find('\n')==0:
                        desc = desc[1:]
                    self.values_desc[self.values[i]] = desc.strip()
            else:
                for i in range(0,len(self.values)):
                    self.values_desc[self.values[i]] = \
                        '%s_%s' % (self.name, self.values[i])
        self.neverEmpty = 0

    def isNeverEmpty(self):
        if self.neverEmpty: return 1
        if self.values != None and len(self.values) > 0:
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
    
    # Targets clasification, for purposes of sorting
    CATEG_ALL       = 0 # target is the 'all' target
    CATEG_NORMAL    = 1 # normal target (exe, lib, dll, phony, ...)
    CATEG_AUTOMATIC = 2 # 'automatic' target (not explicitly specified in
                        # bakefiles, e.g. c-to-obj rules, last in makefiles)
    CATEG_MAX       = 3

    def __init__(self, type, id, condition, pseudo, category):
        self.cond = condition
        self.type = type
        self.id = id
        self.pseudo = pseudo
        self.category = category
        self.vars = {}
        self.vars['id'] = id
        self.vars['type'] = self.type
        xxx = Target.Struct()
        xxx.__dict__ = self.vars
        vars['targets'][id] = xxx

targets = containers.OrderedDictWithClasification(
                                Target.CATEG_MAX,
                                lambda x : x.category)


class Fragment:
    """Part of native makefile copied as-is into generated output."""
    def __init__(self, content):
        self.content = content


# Like mk.vars, but for mk.options (i.e. not "real" variables). It's only
# purpose is to make Python code evaluation easier:
__vars_opt = {}

def getHints(var):
    if var not in vars_hints: return ''
    else: return ','.join(vars_hints[var])

def addOption(opt):
    if opt.name in vars:
        del vars[opt.name]
    options[opt.name] = opt
    __vars_opt[opt.name] = '$(%s)' % opt.name
    vars['OPTIONS'] = ' '.join(mk.options.keys())

def delOption(optname):
    del options[optname]
    del __vars_opt[optname]
    vars['OPTIONS'] = ' '.join(mk.options.keys())

def addCondition(cond):
    conditions[cond.name] = cond

def addCondVar(cv, hints=''):
    if cv.name in vars:
        del vars[cv.name]
    cond_vars[cv.name] = cv
    __vars_opt[cv.name] = '$(%s)' % cv.name
    if hints != '':
        mk.vars_hints[cv.name] = hints.split(',')

def delCondVar(cvname):
    del cond_vars[cvname]
    del __vars_opt[cvname]

def addMakeVar(var, value):
    make_vars[var] = value
    vars[var] = '$(%s)' % var

def addTarget(target):
    # add the target:
    targets[target.id] = target

def addFragment(fragment):
    fragments.append(fragment)

def setVar(name, value, eval=1, target=None, add_dict=None, store_in=None,
           append=0, prepend=0, overwrite=1, makevar=0, hints=''):

    if hints != '':
        mk.vars_hints[name] = hints.split(',')
        
    if store_in != None: store = store_in
    elif target != None: store = target.vars
    else:                store = vars

    if makevar and vars['FORMAT_HAS_VARIABLES'] != '1':
        makevar = 0
    
    if (name in override_vars) and (store == vars):
        return # values of user-overriden variables can't be changed

    if not overwrite:
        if name in store:
            return
        if store == vars and ((name in options) or (name in cond_vars)):
            return

    if store == vars and ((name in options) or (name in cond_vars)):
        if name in options:
            delOption(name)
        else:
            delCondVar(name)
        if config.debug:
            print "[dbg] overwriting option/condvar %s" % name

    if eval:
        try:
            v = evalExpr(value, target=target, add_dict=add_dict)
        except Exception,e:
            raise errors.Error("failed to set variable '%s' with value '%s':  %s" % (name, value, e))
    else:
        v = value
    if makevar:
        addMakeVar(name, v)
    else:
        if (append or prepend) and (name in store):
            if append:
                store[name] = '%s %s' % (store[name], v)
            # note that if prepend=append=1, v is added twice:
            if prepend:
                store[name] = '%s %s' % (v, store[name])
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

def evalCondition(cond, target=None, add_dict=None):
    try:
        return evalExpr('$(%s)' % cond, use_options=0,
                        target=target, add_dict=add_dict)
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

    def safeValue(s):
        return str(s).replace('.','_').replace('/','').replace('\\','').upper()
    cname = '_'.join(['%s_%s' % (e.option.name.upper(), safeValue(e.value)) \
                      for e in condexpr_list])
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

False, True = 0, 1

# cache for compiled Python expressions:
__pyExprPrecompiled = {}

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
   
    v = bottlenecks.ProxyDictionary()
    for x in vlist: v.add(x)
 
    global __curNamespace, __pyExprPrecompiled
    oldNS = __curNamespace
    __curNamespace = v.dict

    # NB: Small percentage of py expressions evaluated during bakefile
    #     processing is evaluated more than once (up to several hundred times).
    #     We can't cache the results because they're evaluated in different
    #     contexts, but we can at least spare the compiler repetitive
    #     translation of Python source code into bytecode by putting compiled
    #     bytecode for every expression into cache. This gains a little
    #     performance (~5-10 %).
    if expr in __pyExprPrecompiled:
        val = eval(__pyExprPrecompiled[expr], globals(), v.dict)
    else:
        c = compile(expr, '<e>', 'eval')
        __pyExprPrecompiled[expr] = c
        val = eval(c, globals(), v.dict)

    if val == True: val = 1
    elif val == False: val = 0
    __curNamespace = oldNS
    return str(val)

__doEvalExpr = bottlenecks.doEvalExpr

def evalExpr(e, use_options=1, target=None, add_dict=None):    
    return __doEvalExpr(e, __evalPyExpr, None,
                        None, # moreArgs
                        use_options,
                        target, 
                        add_dict)


def __recordDeps(mod):
    import dependencies
    modfile = '/%s.py' % mod
    for path in sys.path:
        if os.path.isfile(path+modfile):
            dependencies.addDependency(vars['INPUT_FILE'], config.format,
                                       path+modfile)
            return

def importPyModule(modname):
    try:
        exec('import utils.%s' % modname, globals())
        if config.verbose:
            print 'imported python module utils.%s' % modname
        if config.track_deps:
            __recordDeps('utils/%s' % modname)
    except ImportError: pass

    try:
        exec('import %s' % modname, globals())
        if config.verbose:
            print 'imported python module %s' % modname
        if config.track_deps:
            __recordDeps(modname)
    except ImportError: pass
    if config.debug:
        print '[dbg] --- after importing module %s --' % modname
        print '[dbg] sys.path=%s' % sys.path
        if modname in sys.modules:
            print '[dbg] sys.modules[%s]=%s' % (modname,sys.modules[modname])
        else:
            print '[dbg] module not loaded!'
