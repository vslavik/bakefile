
import mk

def dumpMakefile():
    print '\nVariables:'
    for v in mk.vars:
        print '  %-30s = %s' % (v, mk.vars[v])

    print '\nOptions:'
    for o in mk.options.values():
        print '  %-30s (default:%s,values:%s)' % (o.name, o.default, o.values)

    print '\nConditions:'
    for c in mk.conditions.values():
        print '  %-30s (%s=%s)' % (c.name,c.option.name,c.value)
        
    print '\nConditional variables:'
    for v in mk.cond_vars.values():
        print '  %-30s' % v.name
        for vv in v.values:
            print '    if %-25s = %s' % (vv.cond.name, vv.value)

    print '\nTargets:'
    for t in mk.targets.values():
        print '  %s %s' % (t.type, t.id)
        for v in t.vars:
            print '    %-28s = %s' % (v, t.vars[v])
