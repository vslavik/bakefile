# 
# Final steps of processing. This involves removing pseudo targets and unneeded
# conditions and conditional variables, evaluating variables that are not yet
# fully evaluated (if <set var="..." eval="0">...</set> was used), replacing
# $(option) by native makefile's syntax if it differs, unescaping \$ etc.
#
# $Id$
#

import sys, string
from types import InstanceType, DictType
import mk, errors, config, utils


def finalEvaluation(outputVarsOnly=1):
    """Evaluates all variables, so that unneccessary $(...) parts are
       removed in cases when <set eval="0" ...> was used.

       Noteworthy effect is that after calling this function all variables
       are fully evaluated except for conditional and make vars and options,
       meaning that outputVarsOnly=0 is only needed when running
       finalEvaluation for the first time, because no ordinary variable depends
       (by using $(varname)) on another ordinary variable in subsequent runs.
    """

    mk.__trackUsage = 1
    mk.__resetUsageTracker(reset_coverage=1)

    list = []

    if outputVarsOnly:
        interestingVars = mk.vars['FORMAT_OUTPUT_VARIABLES'].strip().split(',')
        optimizeVars = len(interestingVars) > 0
    else:
        optimizeVars = 0

    for v in mk.make_vars:
        if '$' in mk.make_vars[v]:
            list.append((mk.make_vars,v,None))
    
    for c in mk.cond_vars.values():
        for v in c.values:
            if '$' in v.value:
                list.append((None,v,c.target))

    if optimizeVars:
        for v in interestingVars:
            if v in mk.vars and '$' in mk.vars[v]:
                list.append((mk.vars,v,None))
    else:
        for v in mk.vars:
            if not (type(mk.vars[v]) is InstanceType or
                    type(mk.vars[v]) is DictType):
                if '$' in mk.vars[v]:
                    list.append((mk.vars,v,None))
   
    if optimizeVars:
        for t in mk.targets.values():
            for v in interestingVars:
                if v in t.vars and '$' in t.vars[v]:
                    list.append((t.vars,v,t))
    else:
        for t in mk.targets.values():
            for v in t.vars:
                if not (type(t.vars[v]) is InstanceType or 
                        type(t.vars[v]) is DictType):
                    if '$' in t.vars[v]:
                        list.append((t.vars,v,t))

    
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
                    mk.__usageTracker.pyexprs - mk.__usageTracker.refs > 0) \
                           and ('$' in new):
                    newList.append((dict,obj,target))
            list = newList
    
    if config.verbose:
        sys.stdout.write('substituting variables ')
        sys.stdout.flush()
    iterateModifications(list)
    if config.verbose: sys.stdout.write('\n')
        

def purgeUnusedOptsVars():
    """Removes unused options, conditional variables and make variables. This
       relies on previous call to finalEvaluation() that fills usage maps
       in mk.__usageTracker.map!"""
    if config.verbose:
        sys.stdout.write('purging unused variables')
        sys.stdout.flush()
    toKill = []

    if mk.vars['FORMAT_NEEDS_OPTION_VALUES_FOR_CONDITIONS'] != '0':
        usedOpts = []
        for c in mk.conditions.values():
            usedOpts += [x.option.name for x in c.exprs]
        for o in mk.options:
            if (o not in mk.__usageTracker.map) and (o not in usedOpts):
                toKill.append((mk.options, mk.__vars_opt, o))
    else:
        for o in mk.options:
            if o not in mk.__usageTracker.map:
                toKill.append((mk.options, mk.__vars_opt, o))
    for v in mk.cond_vars:
        if v not in mk.__usageTracker.map:
            toKill.append((mk.cond_vars, mk.__vars_opt, v))
    for v in mk.make_vars:
        if v not in mk.__usageTracker.map:
            toKill.append((mk.make_vars, mk.vars, v))
    if config.verbose:
        sys.stdout.write(': %i of %i\n' % (len(toKill),
                         len(mk.options)+len(mk.cond_vars)+len(mk.make_vars)))
    for dict1, dict2, key in toKill:
        del dict1[key]
        del dict2[key]
    return len(toKill) > 0


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

    
def eliminateDuplicateCondVars():
    """Removes duplicate conditional variables, i.e. if there are two
       cond. variables with exactly same definition, remove them."""

    duplicates = []
   
    if config.verbose:
        sys.stdout.write('eliminating duplicate conditional variables')
        sys.stdout.flush()
        before = len(mk.cond_vars)
    keys = mk.cond_vars.keys()
    lng = len(keys)    
    for c1 in range(0,lng):
        for c2 in range(c1+1,lng):
            cv1 = mk.cond_vars[keys[c1]]
            cv2 = mk.cond_vars[keys[c2]]
            if cv1.equals(cv2):
                duplicates.append((cv1, cv2))
                break

    def commonPrefix(s1, s2):
        prefix = ''
        for i in range(0, min(len(s1), len(s2))):
            if s1[i] != s2[i]: break
            prefix += s1[i]
        return prefix.rstrip('_')

    def commonSuffix(s1, s2):
        suffix = ''
        for i in range(-1, -min(len(s1),len(s2))-1,-1):
            if s1[i] != s2[i]: break
            suffix = s1[i] + suffix
        return suffix.lstrip('_')
    
    for c1,c2 in duplicates:
        s1 = c1.name
        s2 = c2.name
        common = commonPrefix(s1, s2)
        if common == '' or common[0] in string.digits:
            common = commonSuffix(s1, s2)
        if common == '' or common[0] in string.digits:
            common = commonPrefix(s1.strip('_'), s2.strip('_'))
        if common == '' or common[0] in string.digits:
            common = commonSuffix(s1.strip('_'), s2.strip('_'))
        if common == '' or common[0] in string.digits:
            common = 'VAR'
        if common == s1 or common == s2:
            newname = common
        else:
            counter = 0
            newname = common
            while newname in mk.vars or newname in mk.__vars_opt:
                newname = '%s_%i' % (common,counter)
                counter += 1
        del mk.__vars_opt[c1.name]
        del mk.__vars_opt[c2.name]
        del mk.cond_vars[c1.name]
        del mk.cond_vars[c2.name]
        if c1.name != newname:
            mk.vars[c1.name] = '$(%s)' % newname
        if c2.name != newname:
            mk.vars[c2.name] = '$(%s)' % newname
        c1.name = c2.name = newname
        mk.addCondVar(c1)
    
    if config.verbose:
        sys.stdout.write(': %i -> %i\n' % (before, len(mk.cond_vars)))
    
    return len(duplicates) > 0



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
    finalEvaluation(outputVarsOnly=0)

    # eliminate references: 
    utils.__refEval = 1
    finalEvaluation()

    # delete pseudo targets now:
    pseudos = [ t for t in mk.targets if mk.targets[t].pseudo ]
    for t in pseudos: del mk.targets[t]
    
    # remove unused conditions:
    purgeUnusedConditions()
    
    # purge conditional variables that have same value for all conditions:
    if purgeConstantCondVars():
        finalEvaluation()

    # purge unused options, cond vars and make vars:
    while purgeUnusedOptsVars():
        finalEvaluation()
    
    # eliminate duplicates in cond vars:
    if eliminateDuplicateCondVars():
        finalEvaluation()

    # replace \$ with $:
    replaceEscapeSequences()

    if mk.vars['FORMAT_SUPPORTS_CONDITIONS'] != '1':
        import flatten
        flatten.flatten()
