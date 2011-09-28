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

from abc import ABCMeta, abstractmethod

import types
import expr
import error

# Metaclass used for all extensions in order to implement automatic
# extensions registration. For internal use only.
class _ExtensionMetaclass(ABCMeta):
    def __init__(cls, name, bases, dct):
        super(_ExtensionMetaclass, cls).__init__(name, bases, dct)

        assert len(bases) == 1, "multiple inheritance not supported"

        # skip base classes, only register implementations:
        if name == "Extension":
            return
        if cls.__base__ is Extension:
            # initialize list of implementations for direct extensions:
            cls._implementations = {}
            return

        if cls.name is None:
            # This must be a helper class derived from a particular extension,
            # but not a fully implemented extension; see e.g. MakefileToolset
            # base class for MingwToolset, BorlandToolset etc.
            return

        # for "normal" implementations of extensions, find the extension
        # type class (we need to handle the case of deriving from an existing
        # extension):
        base = cls.__base__
        while not base.__base__ is Extension:
            base = base.__base__
        if cls.name in base._implementations:
            existing = base._implementations[cls.name]
            raise RuntimeError("conflicting implementations for %s \"%s\": %s.%s and %s.%s" %
                               (base.__name__,
                                cls.name,
                                cls.__module__, cls.__name__,
                                existing.__module__, existing.__name__))
        base._implementations[cls.name] = cls



# instances of all already requested extensions, keyed by (type,name)
_extension_instances = {}


class Extension(object):
    """
    Base class for all Bakefile extensions.

    Extensions are singletons, there's always only one instance of given
    extension at runtime. Use the get() method called on appropriate extension
    type to obtain it. For example:

        exe = TargetType.get("exe")
        # ...do something with it...

    .. attribute:: name

       Use-visible name of the extension. For example, the name for targets
       extensions is what is used in target declarations; likewise for
       property names.
    """
    __metaclass__ = _ExtensionMetaclass

    @classmethod
    def get(cls, name=None):
        """
        This class method is used to get an instance of an extension. In can
        be used in one of two ways:

        1. When called on an extension type class with *name* argument, it
           returns instance of extension with given name and of the extension
           type on which this classmethod was called:

           >>> bkl.api.Toolset.get("gnu")
               <bkl.plugins.gnu.GnuToolset object at 0x2232950>

        2. When called without the *name* argument, it must be called on
           particular extension class and returns its (singleton) instance:

           >>> GnuToolset.get()
               <bkl.plugins.gnu.GnuToolset object at 0x2232950>

        :param name: Name of the extension to read; this corresponds to
            class' "name" attribute. If not specified, then get() must be
            called on a extension, not extension base class.
        """
        if name is None:
            assert cls.name is not None, \
                   "get() can only be called on fully implemented extension"
            name = cls.name
            # find the extension base class:
            while not cls.__base__ is Extension:
                cls = cls.__base__
        else:
            assert cls.name is None, \
                   "get(name) can only be called on extension base class"

        global _extension_instances
        key = (cls, name)
        if key not in _extension_instances:
            _extension_instances[key] = cls._implementations[name]()
        return _extension_instances[key]

    @classmethod
    def all(cls):
        """
        Returns iterator over instances of all implementations of this extension
        type.
        """
        for name in cls.all_names():
            yield cls.get(name)

    @classmethod
    def all_names(cls):
        """
        Returns names of all implementations of this extension type.
        """
        return cls._implementations.keys()

    @classmethod
    def all_properties_kinds(cls):
        """
        Returns a set of names of all properties attributes in this class.
        These are attributes named "properties" or "properties_<something>",
        e.g. "properties_module" for properties with module scope.
        """
        props = set()
        t = cls
        while t is not types.ObjectType and t is not None:
            props.update(p for p in dir(cls) if p.startswith("properties"))
            t = t.__base__
        return props

    @classmethod
    def all_properties(cls, kind="properties"):
        """
        For derived extension types that have properties
        e.g. :class:`TargetType`), returns iterator over all properties.

        The class must have *class* member variable
        var:`properties` with a list of :class:`bkl.api.Property` instances.
        Base class' properties are automagically scanned too.

        :param kind: Kind (i.e. attribute name) of the properties to list. By
                default, "properties", but may be more specific, e.g.
                "properties_module" or "properties_vs2010".

        .. seealso:: :class:`bkl.api.Property`
        """
        t = cls
        prev_props = None
        while True:
            t_props = getattr(t, kind, None)
            if t_props is None:
                break # we're done, no more properties
            if isinstance(t_props, types.MethodType):
                if t_props.im_func is not prev_props:
                    for p in t_props():
                        yield p
                prev_props = t_props.im_func
            else:
                if t_props is not prev_props:
                    for p in t_props:
                        yield p
                prev_props = t_props
            # else:
            #   derived class didn't define properties of its own and we don't
            #   want to add the same properties twice
            t = t.__base__

    name = None
    _implementations = {}


class Property(object):
    """
    Properties describe variables on targets etc. that are part of the API --
    that is, they have special meaning for the toolset and.
    Unlike free-form variables, properties have a type associated with them
    and any values assigned to them are checked for type correctness. They
    can optionally have a default value, too.

    .. attribute:: name

       Name of the property/variable.

    .. attribute:: type

       Type of the property, as :class:`bkl.vartypes.Type` instance.

    .. attribute:: default

       Default value of the property (as :class:`bkl.expr.Expr` or a function that returns
       an expression) or :const:`None`. If not specified (i.e. :const:`None`), then this
       property is required and must always be set to a value in the bakefile.

    .. attribute:: readonly

       Indicates if the property is read-only. Read-only properties can only
       have the default value and cannot be modified. They are typically
       derived from some other value and exist as a convenience. An example
       of read-only property is the ``id`` property on targets.

    .. attribute:: scope

       Optional scope of the property. May be one of
       :const:`Property.SCOPE_PROJECT`, :const:`Property.SCOPE_MODULE`,
       :const:`Property.SCOPE_TARGET` for any target or target type name
       (e.g. ``exe``) for scoping on specific target name. May be list of
       such items for multiscope properties. Finally, may be :const:`None`
       for default (depending from where the property was obtained from).

    .. attribute:: toolsets

       List of toolset names for toolsets this property applies to.
       This is mostly for documentation purposes, it doesn't affect
       their processing. Is :const:`None` for toolset-agnostic properties.

    .. attribute:: doc

       Optional documentation for the property.

    Example usage:

    .. code-block:: python

       class FooTarget(bkl.api.TargetType):
           name = "foo"
           properties = [
               Property("deps",
                     type=ListType(IdType()),
                     default=[],
                     doc="Target's dependencies (list of IDs).")
           ]
           ...

    """

    # Scopes for properties
    SCOPE_PROJECT = "project"
    SCOPE_MODULE = "module"
    SCOPE_TARGET = "target"

    def __init__(self, name, type, default=None, readonly=False, doc=None):
        self.name = name
        self.type = type
        self.default = default
        self.readonly = readonly
        self.scope = None
        self.toolsets = None
        self.__doc__ = doc

    def default_expr(self, for_obj):
        """
        Returns the value of :attr:`default` expression. Always returns
        an :class:`bkl.expr.Expr` instance, even if the default is
        of a different type.

        :param for_obj: The class:`bkl.model.ModelPart` object to return
            the default for. If the default value is defined, its expression
            is evaluated in the context of *for_obj*.
        """
        if self.default is None:
            raise error.UndefinedError("required property \"%s\" on %s not set" % (self.name, for_obj),
                                       pos=for_obj.source_pos)
        return self._make_expr(self.default, for_obj)

    def _make_expr(self, val, for_obj):
        if (type(val) is types.FunctionType or type(val) is types.MethodType):
            # default is defined as a callback function
            val = val(for_obj)
        if isinstance(val, expr.Expr):
            return val
        elif isinstance(val, types.StringType):
            # parse strings as bkl language expressions, it's too useful to
            return self._parse_expr(val, for_obj)
        elif isinstance(val, list):
            return expr.ListExpr([self._make_expr(x, for_obj) for x in val])
        elif isinstance(val, types.BooleanType):
            return expr.BoolValueExpr(val)
        else:
            assert False, "unexpected default value type: %s" % type(val)

    def _parse_expr(self, e, for_obj):
        from interpreter.builder import Builder
        from parser import get_parser
        location = '("%s" property default: "%s")' % (self.name, e)
        pars = get_parser("%s;" % e, filename=location)
        e = Builder().create_expression(pars.expression().tree, for_obj)
        e = self.type.normalize(e)
        self.type.validate(e)
        return e


class BuildNode(object):
    """
    BuildNode represents a single node in traditional make-style build graph.
    Bakefile's model is higher-level than that, its targets may represent
    entities that will be mapped into several makefile targets. But BuildNode
    is the simplest element of build process: a list of commands to run
    together with dependencies that describe when to run it and a list of
    outputs the commands create.

    Node's commands are executed if either a) some of its outputs doesn't
    exist or b) any of the inputs was modified since the last time the outputs
    were modified.

    .. seealso:: :meth:`bkl.api.TargetType.get_build_subgraph`

    .. attribute:: name

       Name of build node. May be empty. If not empty and the node has no
       output files (i.e. is *phony*), then this name is used in the generated
       makefiles. It is ignored in all other cases.

    .. attribute:: inputs

       List of all inputs for this node. Its items are filenames (as
       :class:`bkl.expr.PathExpr` expressions) or (phony) target names.

    .. attribute:: outputs

       List of all outputs this node generates. Its items are filenames (as
       :class:`bkl.expr.PathExpr` expressions).

       A node with no outputs is called *phony*.

    .. attribute:: commands:

       List of commands to execute when the rebuild condition is met, as
       :class:`bkl.expr.Expr`.
    """
    def __init__(self, commands, inputs=[], outputs=[], name=None):
        self.commands = commands
        self.inputs = inputs
        self.outputs = outputs
        self.name = name
        assert name or outputs, \
               "phony target must have a name, non-phony must have outputs"


class FileType(Extension):
    """
    Description of a file type. File types are used by
    :class:`bkl.api.FileCompiler` to define both input and output files.

    .. attribute:: extensions

       List of extensions for this file type, e.g. ``["cpp", "cxx", "C"]``.
    """
    def __init__(self, extensions=[]):
        self.extensions = extensions

    def detect(self, filename):
        """
        Returns True if the file is of this file type. This method is only
        called if the file has one of the extensions listed in
        :attr:`extensions`. By default, returns True.

        :param filename: Name of the file to check. Note that this is native
                         filename and points to existing file.
        """
        return True


class FileCompiler(Extension):
    """
    In Bakefile API, FileCompiler is used to define all compilation steps.

    Traditionally, the term *compiler* is used for a tool that compiles source
    code into object files. In Bakefile, a *file compiler* is generalization of
    this term: it's a tool that compiles file or files of one object type into
    one or more files of another type. In this meaning, a C/C++ compiler is a
    *file compiler*, but so is a linker (it "compiles" object files into
    executables) or e.g. Lex/Yacc compiler or Qt's MOC preprocessor.
    """
    #: :class:`bkl.api.FileType` for compiler's input file.
    in_type = None

    #: :class:`bkl.api.FileType` for compiler's output file.
    out_type = None

    ONE_TO_ONE  = "1"
    MANY_TO_ONE = "many"

    #: Cardinality of the compiler. That is, whether it compiles one file into
    #: one file (:const:`FileCompiler.ONE_TO_ONE`, e.g. C compilers) or whether
    #: it compiles many files of the same type into one output file
    #: (:const:`FileCompiler.MANY_TO_ONE`, e.g. the linker or Java compiler).
    cardinality = ONE_TO_ONE

    def is_supported(self, toolset):
        """
        Returns whether given toolset is supported by this compiler.

        Default implementation returns True for all toolsets.
        """
        return True

    @abstractmethod
    def commands(self, target, input, output):
        """
        Returns list of commands (as :class:`bkl.expr.Expr`) to invoke
        the compiler.

        :param target: The target object for which the invocation is done.
        :param input:  Input file (:class:`bkl.expr.PathExpr`) or
            files (:class:`bkl.expr.ListExpr`), depending on cardinality.
        :param output: :class:`bkl.expr.Expr` expression with the name of
            output file.
        """
        raise NotImplementedError


class TargetType(Extension):
    """
    Base class for implementation of a new target type.
    """

    #: List of all properties supported on this target type,
    #: as :class:`Property` instances. Note that properties list is
    #: automagically inherited from base classes, if any.
    properties = []

    @abstractmethod
    def get_build_subgraph(self, toolset, target):
        """
        Returns list of :class:`bkl.api.BuildNode` objects with description
        of this target's local part of build graph -- that is, its part needed
        to produce output files associated with this target.

        Usually, exactly one BuildNode will be returned, but it's possible to
        have TargetTypes that correspond to more than one makefile target
        (e.g. libtool-style libraries or gettext catalogs).

        :param toolset: The toolset used (:class:`bkl.api.Toolset`).
        :param target:  Target instance (:class:`bkl.model.Target`).
        """
        raise NotImplementedError


class Toolset(Extension):
    """
    This class encapsulates generating of the project files or makefiles.

    The term "toolset" refers to collection of tools (compiler, linker, make,
    IDE, ...) used to compile programs. For example, "Visual C++ 2008",
    "Visual C++ 2005", "Xcode" or "Borland C++" are toolsets.

    In Bakefile API, this class is responsible for creation of the output. It
    puts all the components (platform-specific commands, make syntax, compiler
    invocation, ...) together and writes out the makefiles or projects.
    """
    #: This toolset's compiler's object files type, as :class:`bkl.api.FileType`.
    # TODO: shouldn't be needed, get_compilation_subgraph() should figure it out.
    object_type = None

    #: List of all properties supported on this target type,
    #: as :class:`Property` instances. Note that properties list is
    #: automagically inherited from base classes, if any.
    properties = []

    @abstractmethod
    def generate(self, project):
        """
        Generates all output files for this toolset.

        :param project: model.Project instance with complete description of the
            output. It was already preprocessed to remove content not relevant
            for this toolset (e.g. targets or sub-modules built conditionally
            only for other toolsets, conditionals that are always true or false
            within the toolset and so on).
        """
        raise NotImplementedError
