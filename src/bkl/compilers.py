#
#  This file is part of Bakefile (http://www.bakefile.org)
#
#  Copyright (C) 2009 Vaclav Slavik
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

#: Native compiler's object files
class ObjectFileType(FileType):
    name = "object"
    def __init__(self):
        FileType.__init__(self, extensions=["o"]) # FIXME: platform


#: Native executable file type
class NativeExeFileType(FileType):
    name = "exe"
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


def get_compiler(ft_from, ft_to):
    """
    Finds the compiler that compiles files of type *ft_from* into *ft_to*.
    Both arguments are :class:`bkl.api.FileType` instances.

    The returned object is a singleton. If such compiler cannot be found,
    returns None.
    """
    # FIXME: this is toolset-specific, add toolset to the key
    key = (ft_from, ft_to)

    global __cache_compilers
    if key not in __cache_compilers:
        __cache_compilers[key] = None
        for c in FileCompiler.all():
            if c.in_type == ft_from and c.out_type == ft_to:
                __cache_compilers[key] = c
                break

    return __cache_compilers[key]


def get_compilation_subgraph(ft_to, outfile, sources):
    """
    Given list of source files (as :class:`bkl.expr.ListExpr`), produces build
    graph with appropriate :class:`bkl.api.BuildNode` nodes.

    :param ft_to:   Type of the output file to compile to.
    :param outfile: Name of the output file (as :class:`bkl.expr.PathExpr`).
    :param sources: List of source files (as :class:`bkl.expr.PathExpr`).
    """
    # FIXME: toolset-specific

    # FIXME: need to account for conditional compilation, i.e. use some
    #        expr.all_possible_elements(sources)
    assert isinstance(sources, expr.ListExpr)
    source_files = sources.as_py() # FIXME: this is wrong, work on exprs!

    # FIXME: support direct many-files-into-one (e.g. java->jar, .cs->exe)
    # compilation too

    objects = []

    for src in source_files:
        # FIXME: use expr.PathExpr and get_extension(), change_extension()
        ext = str(src[src.rfind('.')+1:])
        objname = str(src[:src.rfind('.')]) + '.o' # FIXME

        ft_from = get_file_type(ext)
        compiler = get_compiler(ft_from, ObjectFileType.get())
        if compiler is None:
            raise Error("cannot determine how to compile \"%s\" files into \"%s\"" % (ft_from.name, ObjectFileType.get().name))

        node = BuildNode(commands=compiler.commands(src, objname),
                         inputs=[src],
                         outputs=[objname])
        objects.append(node)

    linker = get_compiler(ObjectFileType.get(), ft_to)
    assert linker

    object_files = [o.outputs[0] for o in objects]
    link_node = BuildNode(commands=linker.commands(" ".join(object_files), outfile),
                          inputs=object_files,
                          outputs=[outfile])

    return [link_node] + objects
