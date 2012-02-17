#
#  This file is part of Bakefile (http://www.bakefile.org)
#
#  Copyright (C) 2009-2012 Vaclav Slavik
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

from api import FileType, FileCompiler, BuildNode
import model
from error import Error
import expr


#: Native executable file type
class NativeExeFileType(FileType):
    name = "exe"
    # FIXME: extensions

#: Native static library file type
class NativeLibFileType(FileType):
    name = "library"
    # FIXME: extensions

#: Native dynamic library file type
class NativeDllFileType(FileType):
    name = "dll"
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
        FileType.__init__(self, extensions=["cpp", "cxx", "C"])



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


def _make_build_nodes_for_file(toolset, target, srcfile, ft_to):
    src = srcfile.filename
    assert isinstance(src, expr.PathExpr)

    ext = src.get_extension()
    objname = expr.PathExpr([expr.LiteralExpr(src.get_basename())],
                            expr.ANCHOR_BUILDDIR,
                            pos=src.pos).change_extension(ft_to.extensions[0])

    ft_from = get_file_type(ext)
    compiler = get_compiler(toolset, ft_from, ft_to)
    if compiler is None:
        # Try to compile into source file, then into binaries. A typical use of
        # this is flex/bison parser generator.
        for ft_source in get_file_types_compilable_into(toolset, ft_to):
            if get_compiler(toolset, ft_from, ft_source) is not None:
                compilables, allnodes = _make_build_nodes_for_file(toolset, target, srcfile, ft_source)
                objects = []
                for o in compilables:
                    for outf in o.outputs:
                        objn, alln = _make_build_nodes_for_file(
                                            toolset,
                                            target,
                                            model.SourceFile(target, outf, None),
                                            ft_to)
                        objects += objn
                        allnodes += alln
                return (objects, allnodes)
        raise Error("don't know how to compile \"%s\" files into \"%s\"" % (ft_from.name, ft_to.name))

    node = BuildNode(commands=compiler.commands(toolset, target, src, objname),
                     inputs=[src],
                     outputs=[objname])
    return ([node], [node])


def get_compilation_subgraph(toolset, target, ft_to, outfile):
    """
    Given list of source files (as :class:`bkl.expr.ListExpr`), produces build
    graph with appropriate :class:`bkl.api.BuildNode` nodes.

    :param toolset: The toolset used (as :class:`bkl.api.Toolset`).
    :param target: The target object for which the invocation is done.
    :param ft_to:   Type of the output file to compile to.
    :param outfile: Name of the output file (as :class:`bkl.expr.PathExpr`).
    """

    # FIXME: support direct many-files-into-one (e.g. java->jar, .cs->exe)
    # compilation too

    objects = []
    allnodes = []

    for srcfile in target.sources:
        try:
            # FIXME: toolset.object_type shouldn't be needed
            obj, all = _make_build_nodes_for_file(toolset, target, srcfile, toolset.object_type)
            objects += obj
            allnodes += all
        except Error as e:
            if e.pos is None:
                e.pos = srcfile.source_pos
            raise

    linker = get_compiler(toolset, toolset.object_type, ft_to)
    assert linker

    object_files = [o.outputs[0] for o in objects]
    link_commands = linker.commands(toolset, target, expr.ListExpr(object_files), outfile)
    link_node = BuildNode(commands=link_commands,
                          inputs=object_files,
                          outputs=[outfile])

    return [link_node] + allnodes
