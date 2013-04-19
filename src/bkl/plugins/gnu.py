#
#  This file is part of Bakefile (http://www.bakefile.org)
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

from bkl.api import FileCompiler, FileType
from bkl.makefile import MakefileToolset, MakefileFormatter, MakefileExprFormatter
import bkl.compilers
import bkl.expr

# FIXME: shouldn't be needed later
from bkl.expr import ListExpr, LiteralExpr, BoolExpr, NonConstError
from bkl.error import Error

# GCC flags for supported architectures:
OSX_ARCH_FLAGS = {
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
cc_is_clang := $(if $(shell $(CC) --version | grep clang),yes,no)
ifeq "$(cc_is_clang)" "yes"
  cc_deps_flags = -MD -MP
  cc_deps_cmd   =
else
  cc_deps_flags =
  cc_deps_cmd   = $1 -M -MP -o $(patsubst %.o,%.d,$@) $2
endif
"""

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

    _compiler = "$(CC)"
    _flags_var_name = "CFLAGS"
    _options_prop_name = "c-compiler-options"

    def commands(self, toolset, target, input, output):
        needs_extra_deps_code = (isinstance(toolset, OSXGnuToolset) and
                                 _is_multiarch_target(target)) # see GCC_DEPS_FLAGS
        cmd = [LiteralExpr("%s -c -o $@ $(CPPFLAGS) $(%s)" %
                (self._compiler, self._flags_var_name))]
        if needs_extra_deps_code:
            cmd += [LiteralExpr("$(cc_deps_flags)")]
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
        if target["warnings"] == "no":
            cmd.append(LiteralExpr("-w"))
        elif target["warnings"] == "all":
            cmd.append(LiteralExpr("-Wall"))
        #else: don't do anything special for "minimal" and "default"
        cmd += target["compiler-options"]
        cmd += target[self._options_prop_name]
        # FIXME: use a parser instead of constructing the expression manually
        #        in here
        cmd.append(input)
        retval = [ListExpr(cmd)]

        if needs_extra_deps_code:
            # add command for generating the deps:
            cmd = [LiteralExpr("$(call cc_deps_cmd,%s,$(CPPFLAGS) $(%s)" %
                    (self._compiler, self._flags_var_name))]
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

    _compiler = "$(CXX)"
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
        if target["multithreading"]:
            cmd.append(LiteralExpr(toolset.pthread_ld_flags))
        return cmd

    def commands(self, toolset, target, input, output):
        cmd = [LiteralExpr("$(CXX) -o $@ $(LDFLAGS)"), input]
        # FIXME: use a parser instead of constructing the expression manually
        #        in here
        cmd += self._linker_flags(toolset, target)
        return [ListExpr(cmd)]


class GnuSharedLibLinker(GnuLinker):
    """
    GNU shared libraries linker.
    """
    name = "GNU shared LD"
    in_type = GnuObjectFileType.get()
    out_type = bkl.compilers.NativeSharedLibraryFileType.get()

    def commands(self, toolset, target, input, output):
        cmd = [LiteralExpr("$(CXX) %s -o $@" % toolset.shared_library_link_flag)]
        if toolset.soname_flags:
            cmd.append(LiteralExpr(toolset.soname_flags))
        cmd.append(LiteralExpr("$(LDFLAGS)"))
        cmd.append(input)
        # FIXME: use a parser instead of constructing the expression manually
        #        in here
        cmd += self._linker_flags(toolset, target)
        return [ListExpr(cmd)]


class GnuLoadableModuleLinker(GnuLinker):
    """
    GNU loadable modules linker.
    """
    name = "GNU module LD"
    in_type = GnuObjectFileType.get()
    out_type = bkl.compilers.NativeLoadableModuleFileType.get()

    def commands(self, toolset, target, input, output):
        cmd = [LiteralExpr("$(CXX) %s -o $@" % toolset.loadable_module_link_flag)]
        cmd.append(LiteralExpr("$(LDFLAGS)"))
        cmd.append(input)
        # FIXME: use a parser instead of constructing the expression manually
        #        in here
        cmd += self._linker_flags(toolset, target)
        return [ListExpr(cmd)]


class GnuLibLinker(GnuFileCompiler):
    """
    GNU library linker.
    """
    name = "AR"
    in_type = GnuObjectFileType.get()
    out_type = bkl.compilers.NativeLibFileType.get()

    def commands(self, toolset, target, input, output):
        # FIXME: use a parser instead of constructing the expression manually
        #        in here
        return [ListExpr([LiteralExpr("$(AR) rcu $@"), input]),
                ListExpr([LiteralExpr("$(RANLIB) $@")])]


class GnuMakefileFormatter(MakefileFormatter):
    """
    Formatter for the GNU Make syntax.
    """
    def var_definition(self, var, value):
        # TODO: use = if it depends on any of the macros defined later
        return "%s ?= %s\n" % (var, " \\\n\t".join(value.split("\n")))

    def submake_command(self, directory, filename, target):
        return "$(MAKE) -C %s -f %s %s" % (directory, filename, target)

    def multifile_target(self, outfiles, deps, commands):
        # Use a helper intermediate target to handle multiple outputs of a rule,
        # because we can't easily use GNU Make's pattern rules matching. The
        # absence of an intermediate file is not a problem and does not cause
        # spurious builds. See for details:
        #   http://www.gnu.org/software/make/manual/html_node/Chained-Rules.html
        #   http://stackoverflow.com/a/10609434/237188
        for c in commands:
            if '$@' in c:
                raise Error("The use of $@ or %%(out) not supported with multiple outputs (in \"%s\")" % c)
        inter_name = ".dummy_" + "_".join(outfiles).replace("/", "_")
        return "\n".join([
            "%s: %s" % (" ".join(outfiles), inter_name),
            ".INTERMEDIATE: %s" % inter_name,
            self.target(inter_name, deps, commands)
            ])


class GnuExprFormatter(MakefileExprFormatter):
    def bool_value(self, e):
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
            return "$(call _equal,%s,%s)" % (l, r)
        if e.operator == BoolExpr.NOT_EQUAL:
            return "$(call _not,$(call _equal,%s,%s))" % (l, r)
        if e.operator == BoolExpr.NOT:
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

    autoclean_extensions = ["o", "d"]
    del_command = "rm -f"

    object_type = GnuObjectFileType.get()

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

    def on_header(self, file, module):
        file.write("""
# This file was automatically generated by bakefile.
#
# Any manual changes will be lost if it is regenerated,
# modify the source .bkl file instead if possible.

# You may define standard make variables such as CFLAGS or
# CXXFLAGS to affect the build. For example, you could use:
#
#      make CXXFLAGS=-g
#
# to build with debug information. The full list of variables
# that can be used by this makefile is:
# AR, CC, CFLAGS, CPPFLAGS, CXX, CXXFLAGS, LD, LDFLAGS, MAKE, RANLIB.
""")

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

        file.write("""
# Use \"make RANLIB=''\" for platforms without ranlib.
RANLIB ?= ranlib
""")
        # TODO: only do this if non-const (depending on
        #       Settings/PlaceholderExpr) IfExpr is present in the file
        file.write(GMAKE_IFEXPR_MACROS)

    def on_phony_targets(self, file, targets):
        file.write(".PHONY: %s\n" % " ".join(targets))

    def on_footer(self, file, module):
        file.write("\n"
                   "# Dependencies tracking:\n"
                   "-include *.d\n")


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

    shared_library_extension = "dylib"
    loadable_module_extension = "bundle"
    loadable_module_link_flag = "-bundle"

    pic_flags = None
    soname_flags = None

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

    shared_library_link_flag  = "-G -pic"
    loadable_module_link_flag = "-G -pic"

    deps_flags = "-xMD"
    pic_flags = "-pic -DPIC"
    pthread_cc_flags = "-D_THREAD_SAFE -mt"
    pthread_ld_flags = "-mt -lpthread"
    soname_flags = "-h $(notdir $@)"
    # FIXME: Do this for C++ only
    extra_link_flags = "-lCstd -lCrun"

    def on_header(self, file, module):
        super(SunCCGnuToolset, self).on_header(file, module)
        file.write("""
CC = suncc
CXX = sunCC

""")
