# 
# Final steps of processing. This involves removing pseudo targets and unneeded
# conditions and conditional variables, evaluating variables that are not yet
# fully evaluated (if <set var="..." eval="0">...</set> was used), replacing
# $(option) by native makefile's syntax if it differs, unescaping \$ etc.
#
# $Id$
#

import sys
from types import InstanceType, DictType
import mk, errors, config, utils


def finalEvaluation():
    """Evaluates all variables, so that unneccessary $(...) parts are
       removed in cases when <set eval="0" ...> was used"""

    mk.__trackUsage = 1
    mk.__resetUsageTracker(reset_coverage=1)

    refs = []
    list = []
    
    for v in mk.vars:
        if not (type(mk.vars[v]) is InstanceType or
                type(mk.vars[v]) is DictType):
            if '$' in mk.vars[v]:
                list.append((mk.vars,v,None))
    
    for v in mk.make_vars:
        if '$' in mk.make_vars[v]:
            list.append((mk.make_vars,v,None))
    
    for t in mk.targets.values():
        for v in t.vars:
            if not (type(t.vars[v]) is InstanceType or 
                    type(t.vars[v]) is DictType):
                if '$' in t.vars[v]:
                    list.append((t.vars,v,t))
            
    for c in mk.cond_vars.values():
        for v in c.values:
            if '$' in v.value:
                list.append((None,v,c.target))
    
    def iterateModifications(list):
        while len(list) > 0:
            newList = []
            if config.verbose:
                sys.stdout.write('[%i]' % len(list))
                sys.stdout.flush()
            for dict, obj, target in list:
                if dict == None:
                    expr = obj.value
                else:
                    expr = dict[obj]
                mk.__resetUsageTracker(reset_coverage=0)
                new = mk.evalExpr(expr, target=target)
                if expr != new:
                    if dict == None: obj.value = new
                    else: dict[obj] = new
                if (mk.__usageTracker.vars + 
                    mk.__usageTracker.pyexprs -  mk.__usageTracker.refs > 0) \
                           and ('$' in new):
                    newList.append((dict,obj,target))
                if mk.__usageTracker.refs > 0:
                    refs.append((dict,obj,target))
            list = newList
    
    if config.verbose:
        sys.stdout.write('substituting variables ')
        sys.stdout.flush()
    iterateModifications(list)
    if config.verbose: sys.stdout.write('\n')
        
    if len(refs) > 0:
        if config.verbose:
            sys.stdout.write('eliminating references ')
            sys.stdout.flush()
        utils.__refEval = 1
        iterateModifications(refs)
        if config.verbose: sys.stdout.write('\n')
        


def purgeConstantCondVars():
    """Removes conditional variables that have same value regardless of the
       condition."""
    # NB: We can't simply remove cond vars that have all their values same
    #     because there is always implicit value '' if none of the conditions
    #     is met. So we can only remove conditional variable in one of these
    #     two cases:
    #        1) All values are same and equal to ''.
    #        2) All values are same and disjunction of the conditions is
    #           tautology. This is not easy to detect and probably not worth
    #           the effort, so we don't do it (yet?) [FIXME]
    
    if config.verbose:
        sys.stdout.write('purging empty conditional variables')
        sys.stdout.flush()
    
    toDel = []
    for c in mk.cond_vars:
        cv = mk.cond_vars[c]
        if len(cv.values) == 0:
            toDel.append((c, ''))
        else:
            val = cv.values[0].value
            if val != '': continue
            purge = 1
            for v in cv.values[1:]:
                if v.value != val:
                    purge = 0
                    break
            if purge: toDel.append((c,val))
    
    if config.verbose:
        sys.stdout.write(': %i of %i\n' % (len(toDel), len(mk.cond_vars)))    
    for c, val in toDel:
        t = mk.cond_vars[c].target
        del mk.cond_vars[c]
        mk.setVar(c, val, target=t)
    return len(toDel) > 0



def purgeUnusedConditions():
    """Removes unused conditions."""

    if config.verbose:
        sys.stdout.write('purging unused conditions')
        sys.stdout.flush()

    toDel = []
    for c in mk.conditions:
        cond = mk.conditions[c]
        used = 0
        for t in mk.targets.values():
            if t.cond == cond:
                used = 1
                break
        if used: continue
        for cv in mk.cond_vars.values():
            for v in cv.values:
                if v.cond == cond:
                    used = 1
                    break
            if used: break
        if used: continue
        toDel.append(c)
    
    if config.verbose:
        sys.stdout.write(': %i of %i\n' % (len(toDel), len(mk.cond_vars)))
    for c in toDel:
        del mk.conditions[c]
    return len(toDel) > 0



def replaceEscapeSequences():
    # Replace all occurences of \$ by $:
    if config.verbose:
        print 'replacing escape sequences'
    for v in mk.vars:
        if not (type(mk.vars[v]) is InstanceType or
                type(mk.vars[v]) is DictType):
            mk.vars[v] = mk.vars[v].replace('\\$', '$')
    for v in mk.make_vars:
        mk.make_vars[v] = mk.make_vars[v].replace('\\$', '$')
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



def finalize():
    # Replace $(foo) for options by config.variableSyntax format:
    for v in mk.__vars_opt:
        mk.__vars_opt[v] = config.variableSyntax % v

    # evaluate variables:
    finalEvaluation()

    # delete pseudo targets now:
    pseudos = [ t for t in mk.targets if mk.targets[t].pseudo ]
    for t in pseudos: del mk.targets[t]
    
    # remove unused conditions:
    purgeUnusedConditions()
    
    # purge conditional variables that have same value for all conditions:
    if purgeConstantCondVars():
        finalEvaluation()

    # replace \$ with $:
    replaceEscapeSequences()

