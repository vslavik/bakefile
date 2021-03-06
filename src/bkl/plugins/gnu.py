#
#  This file is part of Bakefile (http://bakefile.org)
#
#  Copyright (C) 2009-2013 Vaclav Slavik
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

"""
GNU tools (GCC, GNU Make, ...) toolset.
"""

import os.path
from bkl.api import FileCompiler, FileType
from bkl.makefile import MakefileToolset, MakefileFormatter, MakefileExprFormatter
import bkl.compilers
import bkl.expr

# FIXME: shouldn't be needed later
from bkl.expr import ListExpr, LiteralExpr, BoolExpr, NonConstError
from bkl.error import Error

# GCC flags for supported architectures:
OSX_ARCH_FLAGS = {
    'arm64'  : '-arch arm64',
    'x86'    : '-arch i386',
    'x86_64' : '-arch x86_64',
}

def _is_multiarch_target(target):
    """
    Checks if the target builds for >1 archs, i.e. would use more -arch options
    and be incompatible with gcc's -M* flags.
    """
    try:
        return len(target["archs"]) > 1
    except KeyError:
        return False # not an executable


# Apple's GCC doesn't handle the standard -MD -MP flags (which are used to
# generate .d files with object files' dependencies on sources and headers) in presence
# of multiple -arch options. Clang can handle it, but we must support GCC. So we run
# GCC's preprocessor once more to generate the dependencies, but let's not do
# it unless necessary, because it a) costs some time and b) may omit some deps.
GCC_DEPS_FLAGS = "-MD -MP"
OSX_GCC_DEPS_RULES = """
# Support for generating .d files with multiple -arch options:
CC_is_clang := $(if $(shell $(CC) --version | grep clang),yes,no)
CXX_is_clang := $(if $(shell $(CXX) --version | grep clang),yes,no)
ifeq "$(CC_is_clang)" "yes"
  CC_deps_flags = -MD -MP
  CC_deps_cmd   =
else
  CC_deps_flags =
  CC_deps_cmd   = $1 -M -MP -o $(patsubst %.o,%.d,$@) $2
endif
ifeq "$(CXX_is_clang)" "yes"
  CXX_deps_flags = -MD -MP
  CXX_deps_cmd   =
else
  CXX_deps_flags =
  CXX_deps_cmd   = $1 -M -MP -o $(patsubst %.o,%.d,$@) $2
endif
"""

# These are just some unique strings, the exact syntax doesn't matter currently.
GMAKE_IFEXPR_MACROS_PLACEHOLDER = "{{{BKL_GMAKE_IFEXPR_MACROS}}}"
GMAKE_BUILDDIR_DEF_PLACEHOLDER = "{{{BKL_GMAKE_BUILDDIR_DEF}}}"

# GNU Make has some boolean functions, but not all that we need, so define them
GMAKE_IFEXPR_MACROS = """
_true  := true
_false :=
_not    = $(if $(1),$(_false),$(_true_))
_equal  = $(and $(findstring $(1),$(2)),$(findstring $(2),$(1)))

"""


class GnuObjectFileType(FileType):
    name = "gnu-object"
    def __init__(self):
        FileType.__init__(self, extensions=["o"])


class GnuFileCompiler(FileCompiler):
    """Base class for GNU compilers/linkers."""
    def is_supported(self, toolset):
        return isinstance(toolset, GnuToolset)

    # TODO: a hack, not exactly clean
    def _arch_flags(self, toolset, target):
        if isinstance(toolset, OSXGnuToolset):
            flags = []
            for a in target["archs"]:
                a = a.as_py()
                if a in OSX_ARCH_FLAGS:
                    flags.append(LiteralExpr(OSX_ARCH_FLAGS[a]))
            return flags
        else:
            return []


class GnuCCompiler(GnuFileCompiler):
    """
    GNU C compiler.
    """
    name = "GNU C"
    in_type = bkl.compilers.CFileType.get()
    out_type = GnuObjectFileType.get()

    _compiler = "CC"
    _flags_var_name = "CFLAGS"
    _options_prop_name = "c-compiler-options"

    def commands(self, toolset, target, input, output):
        needs_extra_deps_code = (isinstance(toolset, OSXGnuToolset) and
                                 _is_multiarch_target(target)) # see GCC_DEPS_FLAGS
        cmd = [LiteralExpr("$(%s) -c -o $@ $(CPPFLAGS) $(%s)" %
                (self._compiler, self._flags_var_name))]
        if needs_extra_deps_code:
            cmd += [LiteralExpr("$(%s_deps_flags)" % self._compiler)]
        else:
            cmd += [LiteralExpr(toolset.deps_flags)]
        # FIXME: evaluating the flags here every time is inefficient
        cmd += self._arch_flags(toolset, target)
        if toolset.pic_flags and target["pic"]:
            cmd.append(LiteralExpr(toolset.pic_flags))
        if target["multithreading"]:
            cmd.append(LiteralExpr(toolset.pthread_cc_flags))
        cmd += bkl.expr.add_prefix("-D", target["defines"])
        cmd += bkl.expr.add_prefix("-I", target["includedirs"])

        warning_flags = toolset.warning_flags[str(target["warnings"])]
        if warning_flags is not None:
            cmd.append(LiteralExpr(warning_flags))

        cmd += target["compiler-options"]
        cmd += target[self._options_prop_name]
        # FIXME: use a parser instead of constructing the expression manually
        #        in here
        cmd.append(input)
        retval = [ListExpr(cmd)]

        if needs_extra_deps_code:
            # add command for generating the deps:
            cmd = [LiteralExpr("$(call %s_deps_cmd,$(%s),$(CPPFLAGS) $(%s)" %
                    (self._compiler, self._compiler, self._flags_var_name))]
            cmd += bkl.expr.add_prefix("-D", target["defines"])
            cmd += bkl.expr.add_prefix("-I", target["includedirs"])
            cmd += target["compiler-options"]
            cmd += target[self._options_prop_name]
            cmd.append(input)
            cmd.append(LiteralExpr(")"))
            retval.append(ListExpr(cmd))

        return retval


class GnuCXXompiler(GnuCCompiler):
    """
    GNU C++ compiler.
    """
    name = "GNU C++"
    in_type = bkl.compilers.CxxFileType.get()
    out_type = GnuObjectFileType.get()

    _compiler = "CXX"
    _flags_var_name = "CXXFLAGS"
    _options_prop_name = "cxx-compiler-options"


class GnuLinker(GnuFileCompiler):
    """
    GNU executables linker.
    """
    name = "GNU LD"
    in_type = GnuObjectFileType.get()
    out_type = bkl.compilers.NativeProgramFileType.get()

    def _linker_flags(self, toolset, target):
        cmd = self._arch_flags(toolset, target)
        libdirs = target.type.get_libdirs(target)
        if libdirs:
            cmd += bkl.expr.add_prefix("-L", ListExpr(libdirs))
        libs = target.type.get_libfiles(toolset, target)
        ldlibs = target.type.get_ldlibs(target)
        cmd += libs
        cmd += bkl.expr.add_prefix("-l", ListExpr(ldlibs)).items
        cmd += target.type.get_link_options(target)
        if toolset.extra_link_flags:
            cmd.append(LiteralExpr(toolset.extra_link_flags))
        if toolset.pthread_ld_flags and target["multithreading"]:
            cmd.append(LiteralExpr(toolset.pthread_ld_flags))
        return cmd


    def _make_link_commands(self, toolset, target, input, output_flags=None, extra_flags=None):
        """
        Return the list containing the link command taking the specified inputs.

        The output_flags argument contains linker flags controlling the kind of
        output file to generate while extra_flags contain other options. This
        separation is relatively arbitrary and just makes the code using this
        function more convenient to write.

        Notice that if output_flags is specified, we also automatically append
        the necessary linked flags to allow, or disallow, undefined symbols in
        output. This is again just a convenience, as this is only needed by those
        callers of this function that use output_flags.

        Finally, if the target defines a custom value of the outputdir
        property, the list of commands returned by this function also contains
        a command to create the output directory, as it might not exist yet,
        but must in order for the linker to succeed (note that this is done
        only here as compiler commands generate files in the build directory,
        which is global and is created at the top of the makefile, but output
        directories are per target and so can't be handled in the same way).
        """
        cmd = [LiteralExpr("$(CXX)")]
        if output_flags:
            cmd.append(LiteralExpr(output_flags))

            if target["allow-undefined"]:
                undefined_link_flag = toolset.allow_undefined_link_flag
            else:
                undefined_link_flag = toolset.disallow_undefined_link_flag

            if undefined_link_flag:
                cmd.append(LiteralExpr(undefined_link_flag))

        cmd.append(LiteralExpr("-o $@"))
        if extra_flags:
            cmd.append(LiteralExpr(extra_flags))
        cmd.append(LiteralExpr("$(LDFLAGS)"))
        cmd.append(input)
        # FIXME: use a parser instead of constructing the expression manually
        #        in here
        cmd += self._linker_flags(toolset, target)
        cmds = [ListExpr(cmd)]

        if target.is_variable_explicitly_set("outputdir"):
            cmds.insert(0, LiteralExpr("@mkdir -p $(dir $@)"))

        return cmds

    def commands(self, toolset, target, input, output):
        return self._make_link_commands(toolset, target, input)


class GnuSharedLibLinker(GnuLinker):
    """
    GNU shared libraries linker.
    """
    name = "GNU shared LD"
    in_type = GnuObjectFileType.get()
    out_type = bkl.compilers.NativeSharedLibraryFileType.get()

    def commands(self, toolset, target, input, output):
        return self._make_link_commands(toolset, target, input,
                                        toolset.shared_library_link_flag,
                                        toolset.soname_flags)


class GnuLoadableModuleLinker(GnuLinker):
    """
    GNU loadable modules linker.
    """
    name = "GNU module LD"
    in_type = GnuObjectFileType.get()
    out_type = bkl.compilers.NativeLoadableModuleFileType.get()

    def commands(self, toolset, target, input, output):
        return self._make_link_commands(toolset, target, input,
                                        toolset.loadable_module_link_flag)


class GnuLibLinker(GnuFileCompiler):
    """
    GNU library linker.
    """
    name = "AR"
    in_type = GnuObjectFileType.get()
    out_type = bkl.compilers.NativeLibFileType.get()

    def commands(self, toolset, target, input, output):
        return toolset.make_archiver_commands(input)


class GnuMakefileFormatter(MakefileFormatter):
    """
    Formatter for the GNU Make syntax.
    """
    def var_definition(self, var, value):
        # TODO: use = if it depends on any of the macros defined later
        return "%s ?= %s\n" % (var, " \\\n\t".join(value.split("\n")))

    def submake_command(self, directory, filename, target):
        return "$(MAKE) -C %s -f %s %s" % (directory, filename, target)

    def multifile_target(self, outputs, outfiles, deps, commands):
        # Use a helper intermediate target to handle multiple outputs of a rule,
        # because we can't easily use GNU Make's pattern rules matching. The
        # absence of an intermediate file is not a problem and does not cause
        # spurious builds. See for details:
        #   http://www.gnu.org/software/make/manual/html_node/Chained-Rules.html
        #   http://stackoverflow.com/a/10609434/237188
        for c in commands:
            if '$@' in c:
                raise Error("The use of $@ or %%(out) not supported with multiple outputs (in \"%s\")" % c)
        inter_name = ".dummy_" + "_".join("_".join(c.as_py() for c in f.components) for f in outputs)
        return "\n".join([
            "%s: %s" % (" ".join(outfiles), inter_name),
            ".INTERMEDIATE: %s" % inter_name,
            self.target(inter_name, deps, commands)
            ])


class GnuExprFormatter(MakefileExprFormatter):
    def path(self, e):
        # We handle all build paths in a very special way to allow customizing
        # them at make time by setting the make builddir variable, which is
        # used to initialize another make variable called _builddir which is
        # then used to construct all build paths.
        if e.anchor == bkl.expr.ANCHOR_BUILDDIR:
            # Notice that _builddir is either empty or contains the
            # trailing slash, so we must not add another one here.
            self.toolset.uses_builddir = True
            return "$(_builddir)" + "/".join(self.format(c) for c in e.components)

        super_self = super(GnuExprFormatter, self)

        if e.anchor == bkl.expr.ANCHOR_TOP_BUILDDIR:
            self.toolset.uses_builddir = True

            # To handle top build directory-relative paths correctly, just
            # interpret the path relatively to the top source directory.
            p = super_self.path(bkl.expr.PathExpr(e.components, bkl.expr.ANCHOR_TOP_SRCDIR))

            # But then root it at build directory.
            return "$(_builddir)" + p

        return super_self.path(e)

    def bool_value(self, e):
        self.toolset.uses_non_std_bool_macros = True
        return "$(_true)" if e.value else "$(_false)"

    def bool(self, e):
        l = self.format(e.left)
        if e.right is not None:
            r = self.format(e.right)
        if e.operator == BoolExpr.AND:
            return "$(and %s,%s)" % (l, r)
        if e.operator == BoolExpr.OR:
            return "$(or %s,%s)" % (l, r)
        if e.operator == BoolExpr.EQUAL:
            self.toolset.uses_non_std_bool_macros = True
            return "$(call _equal,%s,%s)" % (l, r)
        if e.operator == BoolExpr.NOT_EQUAL:
            self.toolset.uses_non_std_bool_macros = True
            return "$(call _not,$(call _equal,%s,%s))" % (l, r)
        if e.operator == BoolExpr.NOT:
            self.toolset.uses_non_std_bool_macros = True
            return "$(call _not,%s)" % l
        assert False, "invalid operator"

    def if_(self, e):
        try:
            return super(GnuExprFormatter, self).if_(e)
        except NonConstError:
            c = self.format(e.cond)
            y = self.format(e.value_yes)
            n = self.format(e.value_no)
            return "$(if %s,%s,%s)" % (c, y, n)


class GnuToolset(MakefileToolset):
    """
    GNU toolchain for Unix systems.

    This toolset generates makefiles for the GNU toolchain -- GNU Make, GCC compiler,
    GNU LD linker etc. -- running on Unix system.

    Currently, only Linux systems (or something sufficiently compatible) are supported.
    In particular, file extensions and linker behavior (symlinks, sonames) are assumed
    to be Linux ones.

    See :ref:`ref_toolset_gnu-osx` for OS X variant.
    """
    name = "gnu"

    Formatter = GnuMakefileFormatter
    ExprFormatter = GnuExprFormatter
    default_makefile = "GNUmakefile"

    default_cc = "cc"
    default_cxx = "c++"

    autoclean_extensions = ["o", "d"]
    del_command = "rm -f"

    object_type = GnuObjectFileType.get()

    allow_undefined_link_flag = "" # This is the default
    disallow_undefined_link_flag = "-Wl,-z,defs"

    library_prefix = "lib"
    library_extension = "a"
    shared_library_prefix = "lib"
    shared_library_extension = "so"
    shared_library_link_flag = "-shared"
    loadable_module_prefix = ""
    loadable_module_extension = "so"
    loadable_module_link_flag = "-shared"

    deps_flags = GCC_DEPS_FLAGS
    pic_flags = "-fPIC -DPIC"
    pthread_cc_flags = "-pthread"
    pthread_ld_flags = "-pthread"
    soname_flags = "-Wl,-soname,$(notdir $@)"
    extra_link_flags = None

    warning_flags = {
        "no":       "-w",
        "minimal":  None,
        "default":  None,
        "all":      "-Wall",
        "max":      "-Wall -Wextra", # Not really max, more could be added.
    }

    def output_default_flags(self, file, configs):
        """
            Helper of on_header() which outputs default, config-dependent,
            values for all the usual compilation flags.
        """

        # Check if we have any custom configurations: we always have at least
        # two standard ones, "Debug" and "Release".
        if len(configs) > 2:
            # We do, so check which of them should use debug settings and
            # which -- the release ones.
            debug_config, release_config = configs['Debug'], configs['Release']
            debug_configs_names = ['Debug']
            release_configs_names = ['Release']
            for name, config in configs.iteritems():
                if config.derived_from(debug_config):
                    debug_configs_names.append(name)
                elif config.derived_from(release_config):
                    release_configs_names.append(name)

            # Assume that tilde characters are never used in the configuration
            # names (it's certainly not common at the very least).
            non_config_sep = '~~'

            make_test_fmt = 'ifneq (,$(findstring %s$(config)%s,%s%%s%s))' % \
                (non_config_sep, non_config_sep, non_config_sep, non_config_sep)

            make_debug_test = make_test_fmt % non_config_sep.join(debug_configs_names)
            make_release_test = make_test_fmt % non_config_sep.join(release_configs_names)
        else:
            # If we only have the two predefined configs, use simpler tests.
            make_debug_test = 'ifeq ($(config),Debug)'
            make_release_test = 'ifeq ($(config),Release)'

        file.write("""
# You may also specify config=%s
# or their corresponding lower case variants on make command line to select
# the corresponding default flags values.
""" % '|'.join(configs.keys()))

        # Accept configs in lower case too to be more Unix-ish.
        for name in configs:
            file.write(
"""ifeq ($(config),%s)
override config := %s
endif
""" % (name.lower(), name))

        file.write(make_debug_test)
        file.write(
"""
override CPPFLAGS += -DDEBUG
override CFLAGS += -g -O0
override CXXFLAGS += -g -O0
override LDFLAGS += -g
else """
)
        file.write(make_release_test)
        file.write(
"""
override CPPFLAGS += -DNDEBUG
override CFLAGS += -O2
override CXXFLAGS += -O2
else ifneq (,$(config))
$(warning Unknown configuration "$(config)")
endif
""")


    def on_header(self, file, module):
        super(GnuToolset, self).on_header(file, module)

        make_variables = [
            'CC',
            'CFLAGS',
            'CPPFLAGS',
            'CXX',
            'CXXFLAGS',
            'LD',
            'LDFLAGS',
            'MAKE',
        ]

        archiver_definition = self._get_archiver_definition(make_variables)

        file.write("""
# You may define standard make variables such as CFLAGS or
# CXXFLAGS to affect the build. For example, you could use:
#
#      make CXXFLAGS=-g
#
# to build with debug information. The full list of variables
# that can be used by this makefile is:
# %s.
""" % ', '.join(sorted(make_variables)))

        self.output_default_flags(file, module.project.configurations)

        if module.project.settings:
            file.write("""#
# Additionally, this makefile is customizable with the following
# settings:
#
""")
            alls = [(s.name, s["help"]) for s in module.project.settings.itervalues()]
            width = max(len(x[0]) for x in alls)
            fmtstr = "#      %%-%ds  %%s\n" % width
            for name, doc in alls:
                file.write(fmtstr % (name, doc if doc else ""))

        file.write("""%s
CC := %s
CXX := %s
""" % (archiver_definition, self.default_cc, self.default_cxx))

        # This placeholder will be replaced either with the definition of the
        # macros, if they turn out to be really needed, or nothing otherwise.
        file.write(GMAKE_IFEXPR_MACROS_PLACEHOLDER)
        self.uses_non_std_bool_macros = False

        # Similarly, this one will be replaced with the definition of the
        # build directory variable if we are building any files in this
        # makefile or nothing if we don't (this does happen in top level
        # makefiles which just dispatch the work to other makefiles, no need
        # to clutter them).
        file.write(GMAKE_BUILDDIR_DEF_PLACEHOLDER)


    def _get_archiver_definition(self, make_variables):
        """
        Return the definition of the variable, or variables, used for
        creating static libraries and add the names of these variables
        to make_variables.
        """

        # Base class version uses classic ar and ranlib utilitiles.
        make_variables.append('AR')
        make_variables.append('RANLIB')

        # Note that AR is predefined by GNU make.
        return """
# Use \"make RANLIB=''\" for platforms without ranlib.
RANLIB ?= ranlib
"""

    def make_archiver_commands(self, input):
        """
        Return the commands needed to create a static archive from the given
        input.
        """

        # FIXME: use a parser instead of constructing the expression manually
        #        in here
        return [ListExpr([LiteralExpr("$(AR) rc $@"), input]),
                ListExpr([LiteralExpr("$(RANLIB) $@")])]

    def _get_builddir_fragment(self, module):
        # Build the value actually representing the build directory, it is
        # only used here (see GnuExprFormatter.path) and only to initialize
        # the internal _builddir in the fragment below.
        makefile = module["%s.makefile" % self.name]
        rel_dir_comps = makefile.components[:-1]

        # None of the complications is needed in the top level makefile,
        # _builddir is the same as $builddir in it anyhow.
        if rel_dir_comps == []:
            builddir_path = "$(builddir)"
        else:
            # Build the relative path to the top source directory.
            to_top_srcdir = "../"*len(rel_dir_comps)

            # First a hack to ensure we start from the top build directory: we
            # need to do this only if the user-defined builddir is relative at
            # make time, so we check for this by comparing it with its absolute
            # path.
            builddir_path = """\
$(if $(findstring $(abspath $(builddir)),$(builddir)),,%s)\
""" % to_top_srcdir

            # Next the build directory itself, whether relative or absolute.
            builddir_path = builddir_path + "$(builddir)"

            # Finally tackle on the relative path to this directory.
            builddir_path = builddir_path + "/" + "/".join(c.as_py() for c in rel_dir_comps)

        return """
# The directory for the build files, may be overridden on make command line.
builddir = .

ifneq ($(builddir),.)
_builddir := %s/
_builddir_error := $(shell mkdir -p $(_builddir) 2>&1)
$(if $(_builddir_error),$(error Failed to create build directory: $(_builddir_error)))
endif
""" % builddir_path


    def on_phony_targets(self, file, targets):
        file.write(".PHONY: %s\n" % " ".join(targets))

    def on_footer(self, file, module):
        file.replace(GMAKE_IFEXPR_MACROS_PLACEHOLDER,
                     GMAKE_IFEXPR_MACROS if self.uses_non_std_bool_macros
                                         else "")

        file.replace(GMAKE_BUILDDIR_DEF_PLACEHOLDER,
                     self._get_builddir_fragment(module) if self.uses_builddir
                                                         else "")


        if self.uses_builddir:
            file.write("\n"
                       "# Dependencies tracking:\n"
                       "-include $(_builddir)*.d\n")


class OSXGnuToolset(GnuToolset):
    """
    GNU toolchain for OS X.

    This toolset is for building on OS X using makefiles, not Xcode. It
    incorporates some of the oddities of OS X's toolchain and should be used
    instead of :ref:`ref_toolset_gnu`.
    """
    # FIXME: This is temporary solution, will be integrated into GnuToolset
    #        with runtime platform detection.
    name = "gnu-osx"

    default_makefile = "Makefile.osx"

    allow_undefined_link_flag = "-undefined dynamic_lookup"
    disallow_undefined_link_flag = "" # This is the default

    shared_library_extension = "dylib"
    shared_library_link_flag = "-shared"
    loadable_module_extension = "bundle"
    loadable_module_link_flag = "-bundle"

    pic_flags = None
    soname_flags = "-install_name @rpath/$(notdir $@)"
    pthread_ld_flags = None

    def _get_archiver_definition(self, make_variables):
        make_variables.append('LIBTOOL')

        return """
# Note: This must be macOS libtool and not GNU libtool.
LIBTOOL ?= libtool
"""

    def make_archiver_commands(self, input):
        # FIXME: use a parser instead of constructing the expression manually
        #        in here
        return [ListExpr([LiteralExpr("$(LIBTOOL) -static -o $@"), input])]

    def on_footer(self, file, module):
        for t in module.targets.itervalues():
            if _is_multiarch_target(t):
                file.write(OSX_GCC_DEPS_RULES)
                break
        super(OSXGnuToolset, self).on_footer(file, module)


class SunCCGnuToolset(GnuToolset):
    """
    GNU toolchain for Sun CC compiler.

    This toolset is for building using the Sun CC (aka Oracle Studio) toolset.
    """

    # FIXME: This is temporary solution, will be integrated into GnuToolset
    #        with runtime platform detection.
    name = "gnu-suncc"

    default_makefile = "Makefile.suncc"

    default_cc = "suncc"
    default_cxx = "sunCC"

    # When using "-z defs" for shared libraries, _all_ libraries must be
    # specified with this toolchain, even libc and libm, if it is used
    # (and as we can't know whether it is or not, it is better to always
    # include it ending up with an unused library rather than not include it
    # and ending up with broken build).
    allow_undefined_link_flag = ""
    disallow_undefined_link_flag = "-z defs -lm -lc"

    shared_library_link_flag  = "-G -Kpic"
    loadable_module_link_flag = shared_library_link_flag

    deps_flags = "-xMD"
    pic_flags = "-Kpic -DPIC"
    pthread_cc_flags = "-D_THREAD_SAFE -mt"
    pthread_ld_flags = "-mt -lpthread"
    soname_flags = "-h $(notdir $@)"
    # FIXME: Do this for C++ only
    extra_link_flags = "-lCstd -lCrun"

    warning_flags = {
        "no":       "-w",
        "minimal":  None,
        "default":  "+w",
        "all":      "+w2 -xport64=implicit",
        "max":      "+w2 -xport64=full",
    }
