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
    myvars = mk.vars
    mytgt = mk.targets
    
    mk.vars = orig_vars
    mk.targets = orig_targets
    mk.cond_vars = orig_cond_vars
    mk.make_vars = orig_make_vars
    
    return (myvars, mytgt)


def flatten():
    cfgs = [x.values for x in makeConfigs()]
    if config.verbose:
        print '%i configurations' % len(cfgs)

    # remove options and conditional variables:
    mk.__vars_opt = {}
    for opt in mk.options.values():
        if opt.values == None:
            mk.vars[opt.name] = opt.default

    # expand or configurations:
    configs = {}
    for c in cfgs:
        print c
        configs[repr(c)] = flattenConfig(c)
    mk.vars['configurations'] = configs
