
import sys, tempfile, os, os.path, string
import mk, config, errors
import empy.em

class Struct: pass

class Container:
    def __init__(self):
        self.dict = {}
        self.list = []
    def append(self, key, value):
        self.dict[key] = value
        self.list.append(value)
    def __iter__(self):
        return iter(self.list)
    def __getitem__(self, key):
        return self.dict[key]

def __stringify(x):
    if x == None: return ''
    return str(x)

def __valueToPy(v):
    return v.replace('\\', '\\\\')

def __copyMkToVars():
    dict = {}
    
    # Copy variables:
    for v in mk.vars:
        if v == 'targets': continue
        dict[v] = __valueToPy(mk.vars[v].strip())

    # Copy targets information:
    targets = Container()

    priorityTargets = []
    if 'all' in mk.targets:
        priorityTargets.append(mk.targets['all'])
        del mk.targets['all']
        
    for tar in priorityTargets + mk.targets.values():
        t = Struct()
        for v in tar.vars:
            exec('t.%s = """%s"""' % (v, __valueToPy(tar.vars[v].strip())))
        t.cond = tar.cond
        targets.append(t.id, t)
    dict['targets'] = targets

    # Copy options:
    options = Container()
    for opt in mk.options.values():
        o = Struct()
        o.name = opt.name
        o.default = opt.default
        o.defaultStr = __stringify(o.default)
        o.desc = opt.desc
        o.descStr = __stringify(o.desc)
        o.values = opt.values
        if o.values != None: o.valuesStr = '[%s]' % ','.join(o.values)
        else: o.valuesStr = ''
        options.append(o.name, o)
    dict['options'] = options

    # Copy conditional variables:
    cond_vars = Container()
    for cv in mk.cond_vars.values():
        c = Struct()
        c.name = cv.name
        c.values = []
        for v in cv.values:
            vv = Struct()
            vv.value = v.value
            vv.cond = Struct()
            vv.cond.name = v.cond.name
            vv.cond.exprs = v.cond.exprs
            c.values.append(vv)
        cond_vars.append(c.name, c)
        exec('cond_vars.%s = c' % c.name)
    dict['cond_vars'] = cond_vars
 
    return dict

def invoke(method):
    found = 0
    for p in config.searchPath:
        template = os.path.join(p, method)
        if os.path.isfile(template):
            found = 1
            rulesdir = p
            break
    if not found:        
        raise errors.Error("can't find output writer '%s'" % method)
   
    filename = tempfile.mktemp('bakefile')   
    empy.em.invoke(['-I','mk',
                    '-I','writer',
                    '-I','utils',
                    '-I','os,os.path',
                    '-B',
                    '-o',filename,
                    '-E','globals().update(writer.__copyMkToVars())',
                    '-D','RULESDIR="%s"' % rulesdir,
                    template])
    f = open(filename, 'rt')
    txt = f.readlines()
    f.close()
    os.remove(filename)
    return txt

def write():
    outs = {}
    for file, writer in config.to_output:
        try:
            if config.verbose: print 'generating %s...' % file
            ret = invoke(writer)
        except errors.Error, e:
            sys.stderr.write(str(e))
            return 0
        if file in outs:
            outs[file] = outs[file] + ret
        else:
            outs[file] = ret
    
    for file in outs:
        try:
            f = open(file, 'rt')
            txt = f.readlines()
            f.close()
        except IOError:
            txt = None
        if outs[file] != txt:
            f = open(file, 'wt')
            f.writelines(outs[file])
            f.close()
            print 'writing %s' % file
        else:
            print 'no changes in %s' % file
    return 1
