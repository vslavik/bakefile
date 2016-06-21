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
Helpers for working with :class:`bkl.api.FileType` and
:class:`bkl.api.FileCompiler` extensions.
"""

from api import FileType, FileCompiler, BuildNode, BuildSubgraph
import model
from error import Error, error_context
import expr
from expr import format_string

from itertools import izip_longest
from collections import defaultdict


#: Native executable file type
class NativeProgramFileType(FileType):
    name = "program"
    # FIXME: extensions

#: Native static library file type
class NativeLibFileType(FileType):
    name = "library"
    # FIXME: extensions

#: Native shared library file type
class NativeSharedLibraryFileType(FileType):
    name = "shared-library"
    # FIXME: extensions

#: Native runtime-loadable module file type
class NativeLoadableModuleFileType(FileType):
    name = "loadable-module"
    # FIXME: extensions


#: C files
class CFileType(FileType):
    name = "C"
    def __init__(self):
        FileType.__init__(self, extensions=["c"])


#: C++ files
class CxxFileType(FileType):
    name = "C++"
    def __init__(self):
        FileType.__init__(self, extensions=["cpp", "cxx", "cc"])



# misc caches:
__cache_types = None
__cache_compilers = {}
__cache_compilers_initialized = set()

def __ensure_cache_types():
    global __cache_types
    if __cache_types is not None:
        return
    __cache_types = {}
    for ft in FileType.all():
        for ext in ft.extensions:
            __cache_types[ext] = ft

def __ensure_cache_compilers(toolset):
    global __cache_compilers
    global __cache_compilers_initialized
    if toolset in __cache_compilers_initialized:
        return
    for c in FileCompiler.all():
        if c.is_supported(toolset):
            key = (toolset, c.in_type, c.out_type)
            __cache_compilers[key] = c
    __cache_compilers_initialized.add(toolset)


def get_file_type(extension):
    """
    Returns file type instance based on extension.

    The returned object is a singleton.

    >>> a = get_file_type("cpp")
    >>> b = get_file_type("cpp")
    >>> assert a is b
    """
    __ensure_cache_types()
    try:
        return __cache_types[extension]
    except KeyError:
        raise Error("unknown file extension \".%s\"" % extension)


def get_compiler(toolset, ft_from, ft_to):
    """
    Finds the compiler that compiles files of type *ft_from* into *ft_to*.
    Both arguments are :class:`bkl.api.FileType` instances.

    The returned object is a singleton. If such compiler cannot be found,
    returns None.
    """
    __ensure_cache_compilers(toolset)
    try:
        key = (toolset, ft_from, ft_to)
        return __cache_compilers[key]
    except KeyError:
        return None


def get_file_types_compilable_into(toolset, ft):
    """
    Returns file types that can be compiled into *ft*.
    """
    __ensure_cache_compilers(toolset)
    for ts, ft_from, ft_to in __cache_compilers:
        if ts == toolset and ft_to == ft:
            yield ft_from


def _make_build_nodes_for_file(toolset, target, srcfile, ft_to, files_map):
    src = srcfile.filename
    assert isinstance(src, expr.PathExpr)

    ext = src.get_extension()
    # FIXME: don't use target_basename.o form for object files, use just the basename,
    #        unless there's a conflict between two targets
    if srcfile in files_map:
        objbase = files_map[srcfile]
    else:
        objbase = src.get_basename()
    objname = expr.PathExpr([expr.LiteralExpr("%s_%s" % (target.name, objbase))],
                            expr.ANCHOR_BUILDDIR,
                            pos=src.pos).change_extension(ft_to.extensions[0])

    ft_from = get_file_type(ext)
    compiler = get_compiler(toolset, ft_from, ft_to)
    if compiler is None:
        # Try to compile into source file, then into binaries. A typical use of
        # this is flex/bison parser generator.
        for ft_source in get_file_types_compilable_into(toolset, ft_to):
            if get_compiler(toolset, ft_from, ft_source) is not None:
                compilables, allnodes = _make_build_nodes_for_file(toolset, target, srcfile, ft_source, files_map)
                objects = []
                for o in compilables:
                    for outf in o.outputs:
                        objn, alln = _make_build_nodes_for_file(
                                            toolset,
                                            target,
                                            model.SourceFile(target, outf, None),
                                            ft_to,
                                            files_map)
                        objects += objn
                        allnodes += alln
                return (objects, allnodes)
        raise Error("don't know how to compile \"%s\" files into \"%s\"" % (ft_from.name, ft_to.name))

    node = BuildNode(commands=compiler.commands(toolset, target, src, objname),
                     inputs=[src] + list(srcfile["dependencies"]),
                     outputs=[objname],
                     source_pos=srcfile.source_pos)
    return ([node], [node])


def _make_build_nodes_for_generated_file(srcfile):
    commands_var = srcfile["compile-commands"]
    inputs=[srcfile.filename] + list(srcfile["dependencies"])
    outputs = srcfile["outputs"]

    fmt_dict = {"in": "$<"}
    if len(outputs) == 1:
        fmt_dict["out"] = fmt_dict["out0"] = "$@"
    else:
        fmt_dict["out"] = outputs
        idx = 0
        for outN in outputs:
            fmt_dict["out%d" % idx] = outN
            idx += 1

    commands = format_string(commands_var, fmt_dict)

    node = BuildNode(commands=commands,
                     inputs=inputs,
                     outputs=list(outputs),
                     source_pos=commands_var.pos)
    return [node]


def get_compilation_subgraph(toolset, target, ft_to, outfile):
    """
    Given list of source files (as :class:`bkl.expr.ListExpr`), produces build
    subgraph (:class:`bkl.api.BuildSubgraph`) with appropriate
    :class:`bkl.api.BuildNode` nodes.

    :param toolset: The toolset used (as :class:`bkl.api.Toolset`).
    :param target:  The target object for which the invocation is done.
    :param ft_to:   Type of the output file to compile to.
    :param outfile: Name of the output file (as :class:`bkl.expr.PathExpr`).
    """

    # FIXME: support direct many-files-into-one (e.g. java->jar, .cs->exe)
    # compilation too

    objects = []
    allnodes = []
    files_map = disambiguate_intermediate_file_names(target.sources)

    for srcfile in target.sources:
        with error_context(srcfile):
            if not srcfile.should_build(): # TODO: allow runtime decision
                continue
            if srcfile["compile-commands"]:
                allnodes += _make_build_nodes_for_generated_file(srcfile)
            else:
                # FIXME: toolset.object_type shouldn't be needed
                obj, all = _make_build_nodes_for_file(toolset, target, srcfile, toolset.object_type, files_map)
                objects += obj
                allnodes += all
    for srcfile in target.headers:
        with error_context(srcfile):
            if not srcfile.should_build(): # TODO: allow runtime decision
                continue
            if srcfile["compile-commands"]:
                allnodes += _make_build_nodes_for_generated_file(srcfile)

    linker = get_compiler(toolset, toolset.object_type, ft_to)
    assert linker

    object_files = [o.outputs[0] for o in objects]
    link_commands = linker.commands(toolset, target, expr.ListExpr(object_files), outfile)
    link_node = BuildNode(commands=link_commands,
                          inputs=object_files,
                          outputs=[outfile],
                          source_pos=target.source_pos)

    return BuildSubgraph(link_node, allnodes)



def disambiguate_intermediate_file_names(files):
    """
    Given a list of SourceFile objects, finds files that would have
    conflicting object file names (e.g. foo/x.cpp and bar/x.cpp would use
    the same x.obj filename).

    Returns dictionary with SourceFile objects as keys and unambiguous
    basenames (e.g. 'x_foo' and 'x_bar' for the above example). Only files
    with conflicts are included in the dictionary (consequently, it will be
    empty or near-empty most of the time).
    """
    d = defaultdict(list)
    for f in files:
        d[f.filename.get_basename()].append(f)
    mapping = {}
    for base, files in d.iteritems():
        if len(files) > 1:
            # remove longest common prefix, use the rest for the object name:
            #
            # for example, for 'src/foo/a/x.cpp' and 'src/bar/b/x.cpp':
            #   components = [('src','src'), ('foo','bar'), ('a','b')]
            #   difference = [('foo','bar'), ('a','b')]
            #   results = [(fileobj1,'foo','a'), (fileobj2,'bar','b')]
            #   mapping = {
            #     fileobj1 : 'x_fooa',
            #     fileobj2 : 'x_barb',
            #     ...
            #   }
            difference = []
            for c in izip_longest(*(x.filename.components[:-1] for x in files)):
                all_same = all(x == c[0] for x in c)
                if not all_same:
                    difference.append(c)
            results = zip(files, *difference)
            for x in results:
                f = x[0]
                path = ([f.filename.get_basename(), "_"] +
                       list(c for c in x[1:] if c is not None))
                mapping[f] = expr.concat(*path)
    return mapping
