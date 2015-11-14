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

from abc import ABCMeta, abstractmethod
import types
import os.path

import expr
import error

# Metaclass used for all extensions in order to implement automatic
# extensions registration. For internal use only.
class _ExtensionMetaclass(ABCMeta):
    def __init__(cls, name, bases, dct):
        super(_ExtensionMetaclass, cls).__init__(name, bases, dct)

        if len(bases) > 1:
            assert bases[0] is Extension, "multiple inheritance only supported if first base class is Extension"

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

        program = TargetType.get("program")
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

    .. attribute:: scopes

       Optional scope of the property, as list of strings. Each item may be one
       of :const:`Property.SCOPE_PROJECT`, :const:`Property.SCOPE_MODULE`,
       :const:`Property.SCOPE_TARGET` for any target or target type name (e.g.
       ``program``) for scoping on specific target name.

       Finally, may be :const:`None` for default (depending from where the
       property was obtained from).

    .. attribute:: inheritable

       A property is *inheritable* if its value can be specified in the
       (grand-)parent scope. For example, an inheritable property on a target
       may be specified at the module level or even in the parent module; an
       inheritable property on a source file (e.g. "defines") may be specified
       on the target, the module and so on.

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
    SCOPE_MODULE  = "module"
    SCOPE_TARGET  = "target"
    SCOPE_FILE    = "file"
    SCOPE_SETTING = "setting"

    def __init__(self, name, type, default=None, readonly=False,
                 inheritable=False, doc=None):
        self.name = name
        self.type = type
        self.default = default
        self.readonly = readonly
        self.inheritable = inheritable
        self.scopes = None
        self.toolsets = None
        self.__doc__ = doc

    def _scope_is_directly_for(self, model_part):
        """True if the property is defined for this scope."""
        assert self.scopes is not None
        import bkl.model
        for sc in self.scopes:
            if (sc == self.SCOPE_PROJECT and
                    isinstance(model_part, bkl.model.Project)):
                return True
            elif (sc == self.SCOPE_MODULE and
                    isinstance(model_part, bkl.model.Module)):
                return True
            elif (sc == self.SCOPE_TARGET and
                    isinstance(model_part, bkl.model.Target)):
                return True
            elif (sc == self.SCOPE_FILE and
                    isinstance(model_part, bkl.model.SourceFile)):
                return True
            elif (sc == self.SCOPE_SETTING and
                    isinstance(model_part, bkl.model.Setting)):
                return True
            # target type scope:
            elif (isinstance(model_part, bkl.model.Target) and
                        model_part.type.name == sc):
                    return True
        return False

    def _add_scope(self, scope):
        if self.scopes is None:
            self.scopes = [scope]
        else:
            self.scopes.append(scope)

    @property
    def internal(self):
        """
        True if the property is for internal purposes and shouldn't be used by
        users, False otherwise.
        """
        return self.name[0] == "_"

    def default_expr(self, for_obj, throw_if_required):
        """
        Returns the value of :attr:`default` expression. Always returns
        an :class:`bkl.expr.Expr` instance, even if the default is
        of a different type.

        :param for_obj: The class:`bkl.model.ModelPart` object to return
            the default for. If the default value is defined, its expression
            is evaluated in the context of *for_obj*.

        :param throw_if_required: If False, returns NullExpr if the property
            is a required one (doesn't have a default value). If True,
            throws in that case.
        """
        default = self._make_default_expr(self.default, for_obj)
        if default is None:
            if throw_if_required:
                raise error.UndefinedError("required property \"%s\" on %s not set" % (self.name, for_obj),
                                           pos=for_obj.source_pos)
            else:
                return expr.NullExpr()
        return default

    def _make_default_expr(self, val, for_obj):
        if hasattr(val, "__call__"):
            # default is defined as a callback function
            val = val(for_obj)
        if val is None:
            return None
        if isinstance(val, expr.Expr):
            return val
        elif isinstance(val, types.StringType) or isinstance(val, types.UnicodeType):
            # parse strings as bkl language expressions, it's too useful to
            return self._parse_expr(val, for_obj)
        elif isinstance(val, list):
            return expr.ListExpr([self._make_default_expr(x, for_obj) for x in val])
        elif isinstance(val, types.BooleanType):
            return expr.BoolValueExpr(val)
        else:
            assert False, "unexpected default value type: %s" % type(val)

    def _parse_expr(self, e, for_obj):
        from interpreter.builder import Builder
        from parser import get_parser
        pars = get_parser("%s;" % e)
        e = Builder().create_expression(pars.expression().tree, for_obj)
        e = self.type.normalize(e)
        self.type.validate(e)
        return e

    def _add_toolset(self, toolset):
        if self.toolsets:
            self.toolsets.append(toolset)
        else:
            self.toolsets = [toolset]


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

    .. seealso:: :meth:`bkl.api.TargetType.get_build_subgraph`, :class:`bkl.api.BuildSubgraph`

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

    .. attribute:: source_pos

       Source code position of whatever code was the cause for the creation of
       this BuildNode (e.g. associated source file), or :const:`None`.
    """
    def __init__(self, commands, inputs=[], outputs=[], name=None, source_pos=None):
        self.commands = commands
        self.inputs = inputs
        self.outputs = outputs
        self.name = name
        self.source_pos = source_pos
        assert name or outputs, \
               "phony target must have a name, non-phony must have outputs"


class BuildSubgraph(object):
    """
    BuildSubgraph is a collection of :class:`bkl.api.BuildNode` nodes.

    .. attribute:: main

       Primary build node of a target (e.g. its executable file).

    .. attribute:: secondary

       A list of any secondary nodes needed to build the main nodes (e.g.
       object files for target's source files). May be empty.
    """
    def __init__(self, main, secondary=[]):
        self.main = main
        self.secondary = secondary

    def all_nodes(self):
        """Yield all nodes included in the subgraph."""
        yield self.main
        for n in self.secondary:
            yield n


class FileRecognizer(object):
    """
    Mixin base class for extensions that handle certain file types and need to
    be associated with a file automatically. The class provides easy to use
    get_for_file() mechanism.

    To use this class, derive from both :class:`bkl.api.Extension` and this one.
    """

    #: List of file extensions recognized by this extension, without dots
    #: (e.g. ``["vcproj", "vcxproj"]``).
    extensions = []

    def detect(self, filename):
        """
        Returns True if the file *filename* is supported by the class.  Note
        that it is only called if the file has one of the extensions listed in
        :attr:`extensions`. By default, returns :const:`True`.

        :param filename: Name of the file to check. Note that this is native
                         filename (as a string) and points to existing file.
        """
        return True

    @classmethod
    def get_for_file(cls, filename):
        """
        Returns appropriate implementation of the class for given file.

        Throws :class:`bkl.error.UnsupportedError` if no implementation could
        be found.

        :param filename: Name of the file, as a native path.
        """
        ext = os.path.splitext(filename)[1]
        if ext: ext = ext[1:]
        for impl in cls.all():
            if ext in impl.extensions and impl.detect(filename):
                return impl
        raise error.UnsupportedError("unrecognized type of file %s" % filename)


class FileType(Extension, FileRecognizer):
    """
    Description of a file type. File types are used by
    :class:`bkl.api.FileCompiler` to define both input and output files.

    .. attribute:: extensions

       List of extensions for this file type, e.g. ``["cpp", "cxx", "cc"]``.
    """
    def __init__(self, extensions=[]):
        self.extensions = extensions


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
    def commands(self, toolset, target, input, output):
        """
        Returns list of commands (as :class:`bkl.expr.Expr`) to invoke
        the compiler.

        :param toolset: Toolset used.
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
        Returns a :class:`bkl.api.BuildSubgraph` object with description
        of this target's local part of build graph -- that is, its part needed
        to produce output files associated with this target.

        Usually, a BuildSubgraph with just one main BuildNode will be
        returned, but it's possible to have TargetTypes that correspond to more
        than one makefile target (e.g. libtool-style libraries or gettext
        catalogs).

        :param toolset: The toolset used (:class:`bkl.api.Toolset`).
        :param target:  Target instance (:class:`bkl.model.Target`).
        """
        raise NotImplementedError

    def vs_project(self, toolset, target):
        """
        Returns Visual Studio project file object (derived from
        :class:`bkl.plugins.vsbase.VSProjectBase`) if the target type can be
        implemented as a Visual Studio project.

        Implementing this method is strictly optional.
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

    def __str__(self):
        return "toolset %s" % self.name

    #: This toolset's compiler's object files type, as :class:`bkl.api.FileType`.
    # TODO: shouldn't be needed, get_compilation_subgraph() should figure it out.
    object_type = None

    #: List of all properties supported on this target type,
    #: as :class:`Property` instances. Note that properties list is
    #: automagically inherited from base classes, if any.
    properties = []

    @abstractmethod
    def get_builddir_for(self, target):
        """
        Returns build directory used for *target*.

        Returned value must be a :class:`bkl.expr.PathExpr` expression object,
        but it doesn't have to be a constant (for example, it may reference
        configuration name, as e.g. Visual Studio does).

        The function is called after the model is fully loaded and partially
        simplified, on a model already specialized for this toolset only. It is
        used to replace path expression with the relative `@builddir` anchor
        with absolute paths.
        """
        raise NotImplementedError

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


class CustomStep(Extension):
    """
    Custom processing step that is applied to the loaded model.

    Plugins of this kind can be used to perform any custom operations with the
    model. For example, they may enforce coding style, they may add or modify
    some properties or even generate auxiliary output files.

    CustomStep class has several hook methods called at different phases of
    processing. All of them do nothing by default and reimplementing them is
    optional.
    """

    def finalize(self, model):
        """
        Called after loading the model from file(s) and before doing any
        optimizations or error checking on it.

        Do not create any output files here, leave that to :meth:`generate()`.
        """
        pass

    def generate(self, model):
        """
        Called right before generating the output. It is called on the common
        model, before optimizing it for individual toolsets.

        It is permitted to create output files in this method.
        """
        pass
