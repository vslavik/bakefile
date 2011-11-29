#
#  This file is part of Bakefile (http://www.bakefile.org)
#
#  Copyright (C) 2009-2011 Vaclav Slavik
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
__cache_types = {}
__cache_compilers = {}


def get_file_type(extension):
    """
    Returns file type instance based on extension.

    The returned object is a singleton.

    >>> a = get_file_type("cpp")
    >>> b = get_file_type("cpp")
    >>> assert a is b
    """
    global __cache_types
    if extension not in __cache_types:
        for ft in FileType.all():
            if extension in ft.extensions:
                __cache_types[extension] = ft
                return __cache_types[extension]
        raise Error("unknown file extension \".%s\"" % extension)
    return __cache_types[extension]


def get_compiler(toolset, ft_from, ft_to):
    """
    Finds the compiler that compiles files of type *ft_from* into *ft_to*.
    Both arguments are :class:`bkl.api.FileType` instances.

    The returned object is a singleton. If such compiler cannot be found,
    returns None.
    """
    key = (toolset, ft_from, ft_to)

    global __cache_compilers
    if key not in __cache_compilers:
        __cache_compilers[key] = None
        for c in FileCompiler.all():
            if c.in_type == ft_from and c.out_type == ft_to and c.is_supported(toolset):
                __cache_compilers[key] = c
                break

    return __cache_compilers[key]


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

    for srcfile in target.sources:
        try:
            src = srcfile.filename
            assert isinstance(src, expr.PathExpr)

            ext = src.get_extension()
            objname = src.change_extension(toolset.object_type.extensions[0]) # FIXME
            # FIXME: needs to flatten the path too
            objname.anchor = expr.ANCHOR_BUILDDIR

            ft_from = get_file_type(ext)
            # FIXME: toolset.object_type shouldn't be needed
            compiler = get_compiler(toolset, ft_from, toolset.object_type)
            if compiler is None:
                raise Error("don't know how to compile \"%s\" files into \"%s\"" % (ft_from.name, toolset.object_type.name))

            node = BuildNode(commands=compiler.commands(target, src, objname),
                             inputs=[src],
                             outputs=[objname])
            objects.append(node)
        except Error as e:
            if e.pos is None:
                e.pos = srcfile.source_pos
            raise

    linker = get_compiler(toolset, toolset.object_type, ft_to)
    assert linker

    object_files = [o.outputs[0] for o in objects]
    link_commands = linker.commands(target, expr.ListExpr(object_files), outfile)
    link_node = BuildNode(commands=link_commands,
                          inputs=object_files,
                          outputs=[outfile])

    return [link_node] + objects
