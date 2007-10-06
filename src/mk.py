#
#  This file is part of Bakefile (http://www.bakefile.org)
#
#  Copyright (C) 2003-2007 Vaclav Slavik
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

    def __init__(self, name, default, forceDefault, desc, values, values_desc, context):
        self.context = context
        self.name = name
        self.default = default
        self.forceDefault = forceDefault
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

    def evalDefault(self):
        if self.default == None:
            return

        try:
            self.default = evalExpr(self.default, use_options=0)
        except NameError, err:
            raise errors.Error("can't use options or conditional variables in default value of option '%s' (%s)" % (self.name, err),
                               context=self.context)

        # if this is an option with listed values, then the default value
        # which has been specified must be in the list of allowed values:
        if self.values != None and self.default not in self.values:
            # unless the user explicitely wanted to avoid this kind of check:
            if not self.forceDefault:
                print self.context
                raise errors.Error("default value '%s' for option '%s' is not among allowed values (%s)" %
                                  (self.default, self.name, ','.join(self.values)),
                                   context=self.context)




class Condition:
    class Expr:
        def __init__(self, option, value):
            self.option = option
            self.value = value

        def __cmp__(self, other):
            return cmp((self.option, self.value), (other.option, other.value))
        
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
            raise errors.Error("failed to set variable '%s' to value '%s': %s" % (name, value, e))
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
    if expr.find(' or ') != -1:
        raise errors.Error(
                "'%s': only 'and' operator allowed when creating a conditional variable" % expr)
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

def removeCondVarDependencyFromCondition(condvar, condvarvalue):
    """
        Simplifies the condition 'condvar==condvarvalue' to a list of
        conditions referring directly to the option which defines the
        given condvar.

        E.g.
        given a conditional variable defined as:
            <set var="CONDVAR">
            *   <if cond="OPTION1=='Opt1Value1' and
            *             OPTION2=='Opt2Value2'">CondVarValue1</if>
                <if cond="OPTION1=='Opt1Value2'">CondVarValue2</if>
            </set>
        the conditional variable defined as:
            <set var="CONDCONDVAR">
            *   <if cond="CONDVAR=='CondVarValue1'">CondCondVarValue1</if>
                <if cond="CONDVAR=='CondVarValue2'">CondCondVarValue2</if>
            </set>
        is translated by this function to:
            <set var="CONDCONDVAR">
            *   <if cond="OPTION1=='Opt1Value1' and
            *             OPTION2=='Opt2Value2'">CondCondVarValue1</if>
                <if cond="OPTION1=='Opt1Value2'">CondCondVarValue2</if>
            </set>

        i.e. this function operates on the lines marked with *
    """
    # as in example above a single condition for CONDCONDVAR (like
    # CONDVAR=='CondVarValue1') can be translated into multiple conditions
    # against one or more options (like OPTION1=='Opt1Value1' and
    # OPTION2=='Opt2Value2'):
    condexpr_list = []
    converted_cond = ""
    for v in condvar.values:
        if v.value == condvarvalue:
            # ok, we've found the value for CONDVAR which we are
            # searching (i.e. in the sample above 'CondVarValue1')
            for expression in v.cond.exprs:
                # now convert our CONDVAR=='CondVarValue1' expression to
                # the expression which sets CONDVAR deriving it from OPTION*
                condexpr_list.append(Condition.Expr(expression.option,
                                                    expression.value))

                # keep track of the conversion we're doing for debug purpose
                # (see below)
                if config.debug:
                    if converted_cond != "":
                        converted_cond += " and "
                    converted_cond += "%s==%s" % \
                            (expression.option.name, expression.value)

            # conversion done - do not check other possible values of CONDVAR
            break

    # notify the user about this conversion
    if config.debug:
        print "[dbg] the '%s==%s' expression has been converted to '%s'" \
                % (condvar.name, condvarvalue, converted_cond)
    return condexpr_list

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
            # strip quotes from value
            value = value[1:-1]
        else:
            try:
                value = int(value)
            except ValueError:
                return None
        
        if name in options:
            condexpr_list.append(Condition.Expr(options[name], value))
        elif name in cond_vars:
            cvar = cond_vars[name]
            convlist = removeCondVarDependencyFromCondition(cvar, value)
            condexpr_list = condexpr_list + convlist
        else:
            raise errors.Error("conditional variables can only depend on options or other conditional variables and '%s' is not one" % name)

    # optimization: simplify expressions removing redundant terms (A and A => A)
    optimized_list = []
    for a in condexpr_list:
        # add to the optimized list only non-redundant tokens
        if a not in optimized_list:
            optimized_list.append(a)
    condexpr_list = optimized_list

    def safeValue(s):
        return str(s).replace('.','_').replace('/','').replace('\\','').upper()
    
    condexpr_list.sort()
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
    vdict = containers.MergedDict()

    if use_options:
        vdict.add(__vars_opt)
    vdict.add(vars)
    if target != None:
        vdict.add(target.vars)
    if add_dict != None:
        vdict.add(add_dict)

    for d in vdict.dicts:
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

    global __curNamespace, __pyExprPrecompiled
    oldNS = __curNamespace
    __curNamespace = vdict

    # NB: Small percentage of py expressions evaluated during bakefile
    #     processing is evaluated more than once (up to several hundred times).
    #     We can't cache the results because they're evaluated in different
    #     contexts, but we can at least spare the compiler repetitive
    #     translation of Python source code into bytecode by putting compiled
    #     bytecode for every expression into cache. This gains a little
    #     performance (~5-10 %).
    if expr in __pyExprPrecompiled:
        val = eval(__pyExprPrecompiled[expr], globals(), vdict.dictForEval())
    else:
        c = compile(expr, '<e>', 'eval')
        __pyExprPrecompiled[expr] = c
        val = eval(c, globals(), vdict.dictForEval())

    if val == True: val = 1
    elif val == False: val = 0
    __curNamespace = oldNS
    return str(val)

__doEvalExpr = bottlenecks.doEvalExpr

def evalExpr(e, use_options=1, target=None, add_dict=None):    
    try:
        return __doEvalExpr(e, __evalPyExpr, None,
                            None, # moreArgs
                            use_options,
                            target, 
                            add_dict)
    except KeyError, err:
        raise RuntimeError("undefined variable %s" % err)
    except errors.ErrorBase, err:
        raise RuntimeError(err.getErrorMessage())


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
