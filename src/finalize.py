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
                if v in mk.make_vars: continue
                if not (type(mk.vars[v]) is InstanceType or
                        type(mk.vars[v]) is DictType):
                    if '$' in mk.vars[v]:
                        mk.vars[v] = modify(mk.vars[v], mk.evalExpr(mk.vars[v]),
                                            modified)
            for v in mk.make_vars:
                if '$' in mk.make_vars[v]:
                    mk.make_vars[v] = modify(mk.make_vars[v],
                                             mk.evalExpr(mk.make_vars[v]),
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

