# 
# Flattens prepared variables and targets after "finalize" step - i.e. removes
# conditional variables and replaces them with representation with multiple
# _configurations_ (assignments of values to options) and targets assigned to
# them. This is only useful for - and used by - formats that don't support
# variables, such as MSVC project files.
#
# $Id$
#

import config, copy
import errors, mk
import finalize

class Configuration:
    """Configuration description class."""
    def __init__(self):
        self.values = {}

def makeConfigs():
    """Returns list of configurations."""

    def expandCfgs(cfgs, option):
        if option.values == None:
            if option.default == None:
                raise errors.Error("can't flatten makefile: option '%s' does not have default value or list of possible values" % option.name)
            else:
                # the option is irrelevant because we can simply substitute
                # default value:
                if config.verbose:
                    print "using default value '%s' for option '%s'" % \
                          (option.default, option.name)
                return cfgs
        out = []        
        name = option.name
        for c in cfgs:
            for v in option.values:
                x = copy.deepcopy(c)
                x.values[name] = v
                out.append(x)
        return out

    cfgs = []
    for o in mk.options.values():
        if len(cfgs) == 0:
            cfgs = expandCfgs([Configuration()], o)
        else:
            cfgs = expandCfgs(cfgs, o)
    return cfgs
    

configDefs = {}

def __cfg2str(c):
    list = [mk.options[x].values_desc[c[x]] for x in c]
    if len(list) == 0:
        return 'Default'
    else:
        return ' '.join(list)


def flattenConfig(cfg):
    # make copy of mk.vars, we'll need to restore it later:
    orig_vars = mk.vars
    mk.vars = copy.deepcopy(mk.vars)
    orig_targets = mk.targets
    mk.targets = copy.deepcopy(mk.targets)
    orig_make_vars = mk.make_vars
    mk.make_vars = {}
    orig_cond_vars = mk.cond_vars
    mk.cond_vars = {}

    if 'configs' in mk.vars: del mk.vars['configs']
    for t in mk.targets.values():
        if 'configs' in t.vars: del t.vars['configs']
    
    # add option values in this configuration:
    for opt in cfg:
        mk.vars[opt] = cfg[opt]

    # add conditional variables:
    for cv in orig_cond_vars.values():
        mk.vars[cv.name] = ''
        for val in cv.values:
            ok = 1
            for e in val.cond.exprs:
                if e.option.values == None and e.option.default != e.value:
                    ok = 0
                    break
                if cfg[e.option.name] != e.value:
                    ok = 0
                    break
            if not ok: continue
            mk.vars[cv.name] = val.value
            break

    finalize.finalEvaluation()

    # Remove targets that are not part of this configuration:
    toDel = []
    for t in mk.targets:
        tar = mk.targets[t]
        if tar.cond == None:
            use = '1'
        else:
            use = mk.evalCondition(tar.cond.tostr())
        assert use != None
        if use == '0':
            toDel.append(t)
        else:
            orig_targets[t].vars['configs'][__cfg2str(cfg)] = tar.vars

    for t in toDel:
        del mk.targets[t]

    finalize.replaceEscapeSequences()

    myvars = mk.vars
    mytgt = mk.targets
    
    mk.vars = orig_vars
    mk.targets = orig_targets
    mk.cond_vars = orig_cond_vars
    mk.make_vars = orig_make_vars
    
    return (myvars, mytgt)


def findDistinctConfigs(t):
    """Fills t.distinctConfigs which is subset of t.configs where any two
       configs are different. E.g. if there are two configs "Debug ANSI"
       and "Debug Unicode" that have identical variables, they are merged
       into single distinct config "Debug"."""
    configs = t.vars['configs']
    options = configDefs[configs.keys()[0]].keys()

    # try to remove every option and see if it has any effect:
    notNeeded = []
    for o in options:
        if t.cond != None and o in [e.option.name for e in t.cond.exprs]:
            # don't remove option that is part of target's condition - it is
            # present with only one value anyway and we want it to show in
            # config name
            continue
        
        newConfigs = {}
        ok = 1
        for c in configs:
            cdef = copy.copy(configDefs[c])
            del cdef[o]
            name = __cfg2str(cdef)
            if name in newConfigs:
                if newConfigs[name] != configs[c]:
                    ok = 0
                    break
            else:
                newConfigs[name] = configs[c]
        if ok:
            notNeeded.append(o)
    
    dc = {}
    if len(notNeeded) > 0:
        for c in configs:
            cdef = copy.copy(configDefs[c])
            for o in notNeeded:
                del cdef[o]
            dc[__cfg2str(cdef)] = c
    else:
        for c in configs: dc[c] = c
    t.vars['distinctConfigs'] = dc
    

def flatten():        
    cfgs = [x.values for x in makeConfigs()]
    if len(cfgs) == 0:
        cfgs = [{}]

    if config.verbose:
        print '%i configurations' % len(cfgs)
        if config.debug:
            for c in cfgs: print '[dbg] %s' % c

    # remove options and conditional variables:
    mk.__vars_opt = {}
    for opt in mk.options.values():
        if opt.values == None:
            mk.vars[opt.name] = opt.default

    # add target.configs dictionary:
    for t in mk.targets.values():
        t.vars['configs'] = {}

    # expand or configurations:
    configs = {}
    for c in cfgs:
        name = __cfg2str(c)
        configDefs[name] = c
        configs[name] = flattenConfig(c)
    mk.vars['configs'] = configs    

    # reduce number of configurations on targets:
    for t in mk.targets.values():
        findDistinctConfigs(t)
