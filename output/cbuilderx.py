#
# Borland C++ Builder X projects generator script
#  
# Development of this format was sponsored by Borland, thanks!
#
# $Id$

#
# FIXME - TODO:
#  implement missing tags:
#   <cxx-rtti>         (__cxx_rtti)
#   <cxx-exceptions>   (__cxx_exceptions)
#   <warnings>         (__warnings)
#
#

import fnmatch, re
import errors, utils

basename = os.path.splitext(os.path.basename(FILE))[0]
dirname = os.path.dirname(FILE)


# ------------------------------------------------------------------------
#   helpers
# ------------------------------------------------------------------------

def mkConfigID(config):
    return '%s_Build' % (config.replace(' ','_'))

def filterGroups(groups, groupDefs, files):
    """Returns dictionary with files sorted into groups (key: group name).
       Groups are given in 'groups' list of names and 'groupDefs' directory
       as ;-separated wildcards."""
    ret = {}
    used = {}
    for g in groups:
        ret[g] = []
        wildcards = groupDefs[g].split()
        for w in wildcards:
            for f in files:
                if f in used: continue
                if fnmatch.fnmatch(f, w):
                    used[f] = 1
                    ret[g].append(f)
    ret[None] = []
    for f in files:
        if f in used: continue
        ret[None].append(f)
    return ret


# Simple output functions:

output = ''
properties = {}
indentation = ''

def indent():
    flush_properties()
    global indentation
    indentation += '  '

def unindent():
    flush_properties()
    global indentation
    indentation = indentation[2:]

def line(str):
    global indentation, output
    output += '%s%s\n' % (indentation, str)

def property(category, name, value):
    global properties
    properties[(category,name)] = value

def flush_properties():
    global output, properties
    lines = []
    keys = properties.keys()
    keys.sort()
    for category, name in keys:
        line('<property category="%s" name="%s" value="%s"/>' % \
                        (category, name, properties[(category,name)]))
    properties = {}


# ID generator:

lastID = 0
def makeID():
    global lastID
    lastID += 1
    return lastID


# ------------------------------------------------------------------------
#   .bpgr project group file
# ------------------------------------------------------------------------


def genBPGR(targets, cbx_list):
    """Outputs .bpgr project group for 'targets' and stores list of
       (target, filename) toubles into cbx_list list."""

    output = """\
<?xml version="1.0" encoding="UTF-8"?>
<!--Project Group-->
<projectgroup>
"""
    for t in targets:
        output += '  <project path="./%s_%s.cbx"/>\n' % (basename, t.id)
        path = os.path.join(dirname, '%s_%s.cbx' % (basename,t.id))
        cbx_list.append((t,path))
    output += '</projectgroup>\n'
    
    writer.writeFile('%s.bpgr' % (os.path.join(dirname,basename)), output)



def genProjectGroup():
    cbx_list = []

    projects = [t for t in targets if t.__kind == 'project']

    # FIXME -- order it so that the projects can be built in this order!!!
    #  (needed for correct working of .bpgr groups)

    if len(projects) == 0:
        return
    elif len(projects) > 1:
        genBPGR(projects, cbx_list)
    else:
        cbx_list = [(projects[0],
                     os.path.join(dirname, '%s.cbx' % basename))]
    
    for t, filename in cbx_list:
        genCBX(t, filename)
        
    # warn about <action> targets that we can't handle (yet):
    for t in [t for t in targets if t.__kind == 'action']:
        print "warning: ignoring action target '%s'" % t.id


# ------------------------------------------------------------------------
#   .cbx project files
# ------------------------------------------------------------------------

def prepareConfigs(configs):
    """Takes the configurations and organizes them into two level dictionary
       cfgs[config][toolchain]. Returns (order, cfgs)."""

    cfgs = {}
    order = []
    for c in configs_order:
        if c not in configs: continue
        cs = c.split()
        if len(cs) == 1:
            c2 = 'Default'
        else:
            c2 = ' '.join(cs[1:])
        configs[c].__config_name = c2
        c2 = mkConfigID(c2)
        if c2 not in order:
            order.append(c2)
            cfgs[c2] = {}
        cfgs[c2][configs[c].__toolchain] = configs[c]
    
    return (order,cfgs)
                     

def makeToolsetSettings(tool, vars):
    """Prepates build.config.%i, settings.TOOLSET property value."""
    s = 'default;%s' % vars.__debug
    if tool == 'win32b':
        s += ';%s_rtl' % vars.__runtime_libs
        if vars.__threading == 'single':
            s += ';%snonmultithreaded' % vars.__runtime_libs
        else:
            s += ';%smultithreaded' % vars.__runtime_libs
        if vars.__type == 'dllproject':
            s += ';%sthreaded_dll' % vars.__threading
        elif vars.__type == 'exeproject':
            s += ';%sthreaded_%s' % (vars.__threading, vars.__app_type)
    return s


def genCBX(t, filename):
    global output, lastID
    lastID = 0
    
    toolchains = ['MinGW','mswin32','win32b']
    config_list, cfgs = prepareConfigs(t.configs)
    ALL = '*'
    for c in cfgs:
        # for things that are supposed to be same for all toolchains
        cfgs[c][ALL] = cfgs[c]['win32b'] 
    
    # Create file header:
    output = """\
<?xml version="1.0" encoding="UTF-8"?>
<!--C++BuilderX Project-->
<project>
"""
    indent()
    property('build.config', 'active', 0)
    property('build.config', 'count', len(config_list)-1) # -1 is intential
    property('build.config', 'excludedefaultforzero', 0)
    
    # List of configurations:
    for i in range(0, len(config_list)):
        c = config_list[i]
        # buildir can't be toolset specific, pick any one:
        if cfgs[c][ALL].__builddir != '':
            property('build.config.%i' % i, 'builddir',
                                            cfgs[c][ALL].__builddir)
            property('build.config.%i' % i, 'win32.builddir',
                                            cfgs[c][ALL].__builddir)
        property('build.config.%i' % i, 'key', c)
        property('build.config.%i' % i, 'name', cfgs[c][ALL].__config_name)
        property('build.config.%i' % i, 'type', 'Toolset')
        
        for tool in toolchains:
            property('build.config.%i' % i, 'settings.%s' % tool,
                     makeToolsetSettings(tool, cfgs[c][tool]))
            # 'saved' makes our settings effective:
            property('win32.%s.%s' % (tool,c), 'saved', 1)
 
    
    # Basic info           FIXME - use descriptive name of the executable
    property('build.node', 'name', t.id)
    property('build.node', 'type', t.__type)
    property('cbproject', 'lastnodeid', '@LASTNODEID@') # fill me later
    property('cbproject', 'version', 'X.1.0')
    property('unique', 'id', '@LASTNODEID@')
    
    # List the platforms (dummy now, only win32 supported):   
    property('build.platform', 'active', 'win32')
    
    # we don't use these:
    property('build.platform', 'linux.default', 'gnuc++')
    property('build.platform', 'linux.enabled', 0)
    property('build.platform', 'solaris.default', 'gnuc++')
    property('build.platform', 'solaris.enabled', 0)
    
    # but we do use these:
    for c in config_list:
        property('build.platform', 'win32.%s.toolset' % c, CBX_DEFAULT_TOOLCHAIN)
    property('build.platform', 'win32.gnuc++.enabled', 0)
    property('build.platform', 'win32.default', CBX_DEFAULT_TOOLCHAIN)
    for tool in toolchains:
        property('build.platform', 'win32.%s.enabled' % tool, 1)
   
    # if this is executable, add runtime configuration to allow running it:
    if t.__type == 'exeproject':
        property('runtime.0', 'BuildTargetOnRun',
                 'com.borland.cbuilder.build.CBProjectBuilder$ProjectBuildAction;make')
        property('runtime.0', 'ConfigurationName', t.id)
        property('runtime.0', 'RunnableType',
                 'com.borland.cbuilder.runtime.ExecutableRunner')
    else:
        property('runtime', 'ExcludeDefaultForZero', 1)

    # Output misc options:
    for c in config_list:
        outputDefaultSettings(c, cfgs[c])
        outputIncludes(c, cfgs[c])
        outputLibPath(c, cfgs[c])
        outputLibs(c, cfgs[c])
        outputDefines(c, cfgs[c])
        outputAdditionalFlags(c, cfgs[c])
        outputPrecompHeaders(c, cfgs[c])
    outputBuildOrder(t)

    flush_properties()
   
    # Output files:

    # FIXME -- what about files present only in some configs?
    for f in t.__sources.split():
        line('<file path="%s/%s">' % (SRCDIR, f))
        indent()
        property('unique', 'id', makeID())

        # Borland uses g++, must tell it this is C file:
        for c in config_list:
            if f.endswith('.c'):
                setOptionArg('win32.%s.MinGW.g++compile' % c, 'x', 'c')
            outputPrecompHeadersForFile(f, c, cfgs[c])

        unindent()
        line('</file>')
    
    # Footer & output:
    unindent()
    line('</project>')
    output = output.replace('@LASTNODEID@', str(makeID()))    
    writer.writeFile(filename, output)


def enableOption(category, opt):
    property(category, 'option.%s.enabled' % opt, 1)

def disableOption(category, opt):
    property(category, 'option.%s.enabled' % opt, 0)

def setOptionArgs(category, opt, args):
    for i in range(0,len(args)):
        property(category, 'option.%s.arg.%i' % (opt,i+1), args[i])
    enableOption(category, opt)
def setParam(category, opt, args):
    for i in range(0,len(args)):
        property(category, 'param.%s.%i' % (opt,i+1), args[i])

def setOptionArg(category, opt, arg):
    property(category, 'option.%s.arg' % opt, arg)
    enableOption(category, opt)


def outputDefaultSettings(cfg, dicts):
    """Output default settings for toolsets."""
    # MinGW:
    d = dicts['MinGW']
    enableOption('win32.%s.MinGW.g++compile' % cfg, 'c')
    enableOption('win32.%s.MinGW.g++compile' % cfg, 'o')
    enableOption('win32.%s.MinGW.g++compile' % cfg, 'MD')
    setOptionArgs('win32.%s.MinGW.g++compile' % cfg, 'B', ['$(BCB)/MinGW/bin'])
    setOptionArgs('win32.%s.MinGW.g++link' % cfg, 'B', ['$(BCB)/MinGW/bin'])
    enableOption('win32.%s.MinGW.dlltool' % cfg, 'dllname')
    enableOption('win32.%s.MinGW.dlltool' % cfg, 'output-lib')
    if d.__debug == 'debug':
        enableOption('win32.%s.MinGW.g++compile' % cfg, 'g')
        enableOption('win32.%s.MinGW.g++compile' % cfg, 'O0')
        setOptionArg('win32.%s.MinGW.g++link' % cfg, 'g', '2')
    if d.__type == 'exeproject' and \
       d.__app_type == 'gui':
           setOptionArg('win32.%s.MinGW.g++link' % cfg, 'Wl',
                        '--subsystem,windows')
    elif d.__type == 'dllproject':
        enableOption('win32.%s.MinGW.g++compile' % cfg, 'shared')
        if d.__importlib != '':
            setOptionArg('win32.%s.MinGW.g++link' % cfg, 'Wl',
                         '--out-implib,%s%s' % \
                    (d.__targetdir,d.__importlib))
    if d.__type == 'libraryproject':
        setParam('win32.%s.MinGW.ar' % cfg, 'libname',
                      [d.__targetdir+d.__targetname])
    else:
        setOptionArgs('win32.%s.MinGW.g++link' % cfg, 'o',
                      [d.__targetdir+d.__targetname])
    if d.__optimize == 'off':
        enableOption('win32.%s.MinGW.g++compile' % cfg, 'O0')
    else:
        enableOption('win32.%s.MinGW.g++compile' % cfg, 'O2')

    # Borland C++:
    d = dicts['win32b']
    enableOption('win32.%s.win32b.bcc32' % cfg, 'batchfilecompile')
    enableOption('win32.%s.win32b.bcc32' % cfg, 'responsefile')
    enableOption('win32.%s.win32b.bcc32' % cfg, 'V')
    enableOption('win32.%s.win32b.bcc32' % cfg, 'Ve')
    enableOption('win32.%s.win32b.bcc32' % cfg, 'Vx')
    enableOption('win32.%s.win32b.bcc32' % cfg, 'c')
    enableOption('win32.%s.win32b.bcc32' % cfg, 'X')
    enableOption('win32.%s.win32b.bcc32' % cfg, 'a8')
    setOptionArg('win32.%s.win32b.bcc32' % cfg, 'g', 0) # no warning-is-error
    setOptionArg('win32.%s.win32b.tlib' % cfg, 'P', 2048)
    if d.__debug == 'debug':        
        enableOption('win32.%s.win32b.bcc32' % cfg, 'k')
        enableOption('win32.%s.win32b.bcc32' % cfg, 'y')
        enableOption('win32.%s.win32b.bcc32' % cfg, 'v')
        enableOption('win32.%s.win32b.bcc32' % cfg, 'Hc')
    else:
        enableOption('win32.%s.win32b.bcc32' % cfg, 'vi')
        enableOption('win32.%s.win32b.bcc32' % cfg, 'r')
    if d.__runtime_libs == 'dynamic':
        enableOption('win32.%s.win32b.bcc32' % cfg, 'tWR')
    if d.__type == 'dllproject':
        enableOption('win32.%s.win32b.bcc32' % cfg, 'tWD')
    if d.__threading == 'multi':
        enableOption('win32.%s.win32b.bcc32' % cfg, 'tWM')
    elif d.__type == 'exeproject':
        if d.__app_type == 'console':
            enableOption('win32.%s.win32b.bcc32' % cfg, 'tWC')
            enableOption('win32.%s.win32b.ilink32' % cfg, 'ap')
        else:
            enableOption('win32.%s.win32b.bcc32' % cfg, 'tW')
            enableOption('win32.%s.win32b.ilink32' % cfg, 'aa')
    if d.__type == 'libraryproject':
        property('win32.%s.win32b.tlib' % cfg, 'param.libname.1',
                      d.__targetdir+d.__targetname)
        property('win32b.ilink32', 'enabled', 0)
    else:
        property('win32.%s.win32b.ilink32' % cfg, 'param.exefile.1',
                      d.__targetdir+d.__targetname)
    if d.__optimize == 'off':
        enableOption('win32.%s.win32b.bcc32' % cfg, 'Od')
    elif d.__optimize == 'size':
        enableOption('win32.%s.win32b.bcc32' % cfg, 'O1')
    else:
        enableOption('win32.%s.win32b.bcc32' % cfg, 'O2')

    # Visual C++:
    d = dicts['mswin32']
    enableOption('win32.%s.mswin32.MSCL' % cfg, 'NOLOGO')
    enableOption('win32.%s.mswin32.Librarian' % cfg, 'NOLOGO')
    enableOption('win32.%s.mswin32.Linker' % cfg, 'NOLOGO')
    enableOption('win32.%s.mswin32.Linker' % cfg, 'responsefile')
    enableOption('win32.%s.mswin32.MSCL' % cfg, 'COMPILEONLY')
    enableOption('win32.%s.mswin32.MSCL' % cfg, 'NOTSPECIFIEDSMA')
    enableOption('win32.%s.mswin32.MSCL' % cfg, 'NOTSPECIFIEDML')
    enableOption('win32.%s.mswin32.MSCL' % cfg, 'NOINTEL')
    enableOption('win32.%s.mswin32.MSCL' % cfg, 'NOCALL')
    enableOption('win32.%s.mswin32.MSCL' % cfg, 'NOFIX')
    enableOption('win32.%s.mswin32.MSCL' % cfg, 'NOCHECK')
    enableOption('win32.%s.mswin32.MSCL' % cfg, 'NOMACHINE')
    enableOption('win32.%s.mswin32.MSCL' % cfg, 'NOALLFILES')
    enableOption('win32.%s.mswin32.MSCL' % cfg, 'EHs')
    enableOption('win32.%s.mswin32.MSCL' % cfg, 'CPPRTTI') # FIXME - make this configurable(?)
    if d.__debug == 'debug':
        enableOption('win32.%s.mswin32.Linker' % cfg, 'DEBUG')
        enableOption('win32.%s.mswin32.MSCL' % cfg, 'FULLDEBUG')
    else:
        enableOption('win32.%s.mswin32.Linker' % cfg, 'RELEASE')
        enableOption('win32.%s.mswin32.MSCL' % cfg, 'MAXIMUM')
    if d.__type == 'libraryproject':
        setOptionArgs('win32.%s.mswin32.Librarian' % cfg, 'OUT',
                      [d.__targetdir+d.__targetname])
    else:
        setOptionArgs('win32.%s.mswin32.Linker' % cfg, 'OUT',
                      [d.__targetdir+d.__targetname])
        if d.__type == 'exeproject':
            if d.__app_type == 'gui':
                enableOption('win32.%s.mswin32.Linker' % cfg, 'WINDOWS')
            else:
                enableOption('win32.%s.mswin32.Linker' % cfg, 'CONSOLE')
        elif d.__type == 'dllproject':
                enableOption('win32.%s.mswin32.Linker' % cfg, 'DLL')
    if d.__optimize == 'off':
        enableOption('win32.%s.mswin32.MSCL' % cfg, 'DISABLEOPTIMIZATIONS')
    elif d.__optimize == 'size':
        enableOption('win32.%s.mswin32.MSCL' % cfg, 'SIZE')
    else:
        enableOption('win32.%s.mswin32.MSCL' % cfg, 'SPEED')
    if d.__runtime_libs == 'dynamic':
        if d.__debug == 'debug':
            enableOption('win32.%s.mswin32.MSCL' % cfg, 'MSVCRTD')
        else:
            enableOption('win32.%s.mswin32.MSCL' % cfg, 'MSVCRT')
    else:
        if d.__threading == 'single': thr=''
        else: thr='MT'
        if d.__debug == 'debug': dbg='D'
        else: dbg=''
        enableOption('win32.%s.mswin32.MSCL' % cfg, 'LIBC%s%s' % (thr,dbg))



def outputIncludes(cfg, dicts):
    """Include files search paths."""
    # MinGW:
    values = ['$(BCB)\\mingw\\include','$(BCB)\\mingw\\include\\c++\\3.2'] + \
             dicts['MinGW'].__include_paths.split()
    setOptionArgs('win32.%s.MinGW.g++compile' % cfg, 'I', values)
    setOptionArgs('win32.%s.MinGW.windres' % cfg, 'INCLUDEPATH', values)
    # Borland C++:
    values = ['$(BCB)\\include'] + dicts['win32b'].__include_paths.split()
    setOptionArgs('win32.%s.win32b.bcc32' % cfg, 'I', values)
    setOptionArgs('win32.%s.win32b.brcc32' % cfg, 'INCLUDEPATH', values)
    # Visual C++:
    values =  ['$(MICROSOFTWINIA32_INCLUDES)','$(INCLUDE)'] + \
              dicts['mswin32'].__include_paths.split()
    setOptionArgs('win32.%s.mswin32.MSCL' % cfg, 'INCLUDEPATH', values)
    setOptionArgs('win32.%s.mswin32.ResComp' % cfg, 'INCLUDEPATH', values)


def outputLibPath(cfg, dicts):
    # MinGW:
    values = dicts['MinGW'].__lib_paths.split()
    setOptionArgs('win32.%s.MinGW.g++link' % cfg, 'L', values)
    # Borland C++:
    values = ['$(BCB)\\lib'] + dicts['win32b'].__lib_paths.split()
    setOptionArgs('win32.%s.win32b.bcc32' % cfg, 'L', values)
    setOptionArgs('win32.%s.win32b.ilink32' % cfg, 'L', values)
    # Visual C++:
    values = ['$(MICROSOFTWINIA32_LIBS)','$(LIB)'] + \
              dicts['mswin32'].__lib_paths.split()
    setOptionArgs('win32.%s.mswin32.Linker' % cfg, 'LIBPATH', values)


def outputLibs(cfg, dicts):
    # MinGW:
    values = dicts['MinGW'].__ldlibs.split()
    setOptionArgs('win32.%s.MinGW.g++link' % cfg, 'l', values)

    # Borland C++:
    BCC_IGNORE_LIBS = ['user32','gdi32','comdlg32','winspool','winmm',
                       'shell32','comctl32','odbc32','ole32','oleaut32',
                       'uuid','rpcrt4','advapi32','wsock32','kernel32',
                       'opengl32','glu32']
    def mkLibName(x):
        if x.endswith('.lib'): return x
        else: return '%s.lib' % x
    libs = [mkLibName(x) for x in dicts['win32b'].__ldlibs.split() \
            if x not in BCC_IGNORE_LIBS]
    d = dicts['win32b']
    if d.__runtime_libs == 'dynamic' and d.__threading == 'multi':
        libs.append('cw32mti.lib')
    elif d.__runtime_libs == 'dynamic' and d.__threading == 'single':
        libs.append('cw32i.lib')
    elif d.__runtime_libs == 'static' and d.__threading == 'multi':
        libs.append('cw32mt.lib')
    elif d.__runtime_libs == 'static' and d.__threading == 'single':
        libs.append('cw32.lib')
    libs.append('import32.lib')
    setParam('win32.%s.win32b.ilink32' % cfg, 'libfiles', libs)
    object=''
    if d.__type == 'dllproject':
        object = 'c0d32.obj'
    elif d.__type == 'exeproject':
        if d.__app_type == 'console': object = 'c0x32.obj'
        else: object = 'c0w32.obj'
    if object != '':
        property('win32.%s.win32b.ilink32' % cfg, 'param.objfiles.1', object)

    # Visual C++:
    libs = [mkLibName(x) for x in dicts['mswin32'].__ldlibs.split()]
    setParam('win32.%s.mswin32.Linker' % cfg, 'libfiles', libs)


def outputDefines(cfg, dicts):
    # MinGW:
    values = dicts['MinGW'].__defines.split()
    setOptionArgs('win32.%s.MinGW.g++compile' % cfg, 'D_MACRO_VALUE', values)
    setOptionArgs('win32.%s.MinGW.windres' % cfg, 'd', values)
    
    # Borland C++:
    d = dicts['win32b']
    values = d.__defines.split()
    if d.__debug == 'debug':
        values.append('_DEBUG')
    if d.__runtime_libs == 'dynamic':
        values.append('_RTLDLL')
    setOptionArgs('win32.%s.win32b.bcc32' % cfg, 'D', values)
    setOptionArgs('win32.%s.win32b.brcc32' % cfg, 'D', values)
    
    # Visual C++:
    d = dicts['mswin32']
    values = ['WIN32'] + d.__defines.split()
    if d.__debug == 'debug':
        values.append('_DEBUG')
    if d.__type == 'exeproject':
        if d.__app_type == 'gui':
            values.append('_WINDOWS')
        else:
            values.append('_CONSOLE')
    setOptionArgs('win32.%s.mswin32.MSCL' % cfg, 'DEFINEMACRO', values)
    setOptionArgs('win32.%s.mswin32.ResComp' % cfg, 'd', values)



def outputAdditionalFlags(cfg, dicts):
    # MinGW:
    d = dicts['MinGW']
    if d.__threading == 'multi':
        d.__ldflags += ' -mthreads'
    if d.__cppflags != '':
        property('win32.%s.MinGW.g++compile' % cfg,
                 'param.additionalflags', d.__cppflags)
    if d.__ldflags != '':
        property('win32.%s.MinGW.g++link' % cfg,
                 'param.additionalflags', d.__ldflags)

    # Borland C++:
    d = dicts['win32b']
    if d.__cppflags != '':
        property('win32.%s.win32b.g++compile' % cfg,
                 'param.additionalflags', d.__cppflags)
    if d.__ldflags != '':
        property('win32.%s.win32b.g++link' % cfg,
                 'param.additionalflags', d.__ldflags)
    
    # Visual C++:
    d = dicts['mswin32']
    if d.__pch_file != '':
        if d.__builddir=='': filename = d.__pch_file
        else: filename = '%s\\%s' % (d.__builddir, d.__pch_file)
        d.__cppflags += ' /Fp%s.pch' % filename
    if d.__cppflags != '':
        property('win32.%s.mswin32.MSCL' % cfg,
                 'param.additionalflags', d.__cppflags)
    if d.__ldflags != '':
        property('win32.%s.mswin32.Linker' % cfg,
                 'param.additionalflags', d.__ldflags)

            
            
def outputPrecompHeaders(cfg, dicts):
    # Borland C++:
    d = dicts['win32b']
    if d.__pch_use_pch == 'on':
        enableOption('win32.%s.win32b.bcc32' % cfg, 'Hu')
    if d.__pch_file != '':
        if d.__builddir=='': filename = d.__pch_file
        else: filename = '%s\\%s' % (d.__builddir, d.__pch_file)
        setOptionArgs('win32.%s.win32b.bcc32' % cfg, 'H=',
                     ['%s.csm' % filename])
            
    # Visual C++:
    d = dicts['mswin32']
    if d.__pch_use_pch == 'on':
        if d.__pch_generator != '':
            if d.__pch_header != '':
                setOptionArgs('win32.%s.mswin32.MSCL' % cfg, 'USEPRECOMP',
                              [d.__pch_header])
            else:
                enableOption('win32.%s.mswin32.MSCL' % cfg, 'USEPRECOMP')
        else:
            enableOption('win32.%s.mswin32.MSCL' % cfg, 'AUTOMATEPRECOMP')
 

def outputPrecompHeadersForFile(f, cfg, dicts):
    # Borland C++:
    d = dicts['win32b']
    if d.__pch_use_pch == 'on':
        if f in d.__pch_excluded.split() or f == d.__pch_generator:
            disableOption('win32.%s.win32b.bcc32' % cfg, 'Hu')
        if f == d.__pch_generator:
            enableOption('win32.%s.win32b.bcc32' % cfg, 'H')
    # Visual C++:
    d = dicts['mswin32']
    if d.__pch_use_pch == 'on':
        if f in d.__pch_excluded.split():
            disableOption('win32.%s.mswin32.MSCL' % cfg, 'USEPRECOMP')
        if f == d.__pch_generator:
            if d.__pch_header != '':
                setOptionArgs('win32.%s.mswin32.MSCL' % cfg, 'CREATEPRECOMP',
                              [d.__pch_header])
            else:
                enableOption('win32.%s.mswin32.MSCL' % cfg, 'CREATEPRECOMP')


def outputBuildOrder(t):
    if t.__pch_use_pch == 'on' and t.__pch_generator != '':
        srcfiles = t.__sources.split()
        idx = srcfiles.index(t.__pch_generator)
        property('buildorder', 'node.1', 1+idx)
        order = 2
        for i in range(0,len(srcfiles)):
            if i == idx: continue
            property('buildorder', 'node.%i' % order, 1+i)
            order += 1
        property('sys', 'PM_BuildOrder', 1)



genProjectGroup()
