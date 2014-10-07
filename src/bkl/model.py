#
#  This file is part of Bakefile (http://bakefile.org)
#
#  Copyright (C) 2008-2013 Vaclav Slavik
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

import os.path
import copy

import logging
logger = logging.getLogger("bkl.model")

import error, vartypes, utils
import props
import expr
from utils import memoized_property

class Variable(object):
    """
    A Bakefile variable.

    Variables can be either global or target-specific. Value held by a variable
    is stored as expression tree, it isn't evaluated into string form until
    the final stage of processing, when output is generated.

    Variables are typed.

    .. attribute:: name

       Name of the variable.

    .. attribute:: type

       Type of the property, as :class:`bkl.vartypes.Type` instance.

    .. attribute:: value

       Value of the variable, as :class:`bkl.expr.Expr` object.

    .. attribute:: readonly

       Indicates if the variable is read-only. Read-only variables can only
       be assigned once and cannot be modified afterwards.

    .. attribute:: is_property

       Indicates if the variable corresponds to a property.

    .. attribute:: is_explicitly_set

       Indicates if the value was set explicitly by the user.
       Normally true, only false for properties' default values.
    """
    def __init__(self, name, value, type=None, readonly=False, source_pos=None):
        self.name = name
        if type is None:
            type = vartypes.TheAnyType
        self.type = type
        self.value = value
        self.readonly = readonly
        self.is_property = False
        self.is_explicitly_set = True
        self.pos = source_pos

    @staticmethod
    def from_property(prop, value=None):
        """
        Creates a variable from property *prop*. In particular, takes the type
        and :attr:`readonly` attribute from the property. Properties' default
        value is *not* assigned; *value* is used instead.
        """
        v = Variable(name=prop.name,
                     value=value,
                     type=prop.type,
                     readonly=prop.readonly)
        v.is_property = True
        return v

    def set_value(self, value):
        """
        Sets new value on the variable. The new value must have same type
        as current value. Read-only variable cannot be set.

        :param value: New value as :class:`bkl.expr.Expr` object.
        """
        if self.readonly:
            raise error.Error("variable \"%s\" is read-only" % self.name)
        # FIXME: type checks
        self.value = value


class Configuration(object):
    """
    Class representing a configuration.

    Each model has two special configurations, Debug and Release, predefined.

    .. attribute:: name

       Name of the configuration

    .. attribute:: base

       Base configuration this one is derived from, as a :class:`Configuration`
       instance, or :const:`None` for "Debug" and "Release" configurations.

    .. attribute:: is_debug

       Is this a debug configuration?

    .. attribute:: source_pos

       Source code position of object's definition, or :const:`None`.
    """
    def __init__(self, name, base, is_debug, source_pos=None):
        self.name = name
        self.base = base
        self.is_debug = is_debug
        self.source_pos = source_pos
        # for internal use, this is a list of AST nodes that
        # define the configuration
        self._definition = []

    def create_derived(self, new_name, source_pos=None):
        """Returns a new copy of this configuration with a new name."""
        return Configuration(new_name, self, self.is_debug, source_pos)

    def derived_from(self, cfg):
        """
        Returns true if *self* derives, directly or indirectly, from
        configuration *cfg*.

        Returns 0 if not derived. Returns degree of inheritance if derived: 1
        if *cfg* is a direct base, 2 if it is a base of *self*'s base etc.
        """
        if self.base is cfg:
            return 1
        elif self.base is None:
            return 0
        else:
            b = self.base.derived_from(cfg)
            if b:
                return b + 1
            else:
                return 0


class Template(object):
    """
    A template.

    .. attribute:: name

       Name of the template.

    .. attribute:: bases

       List of base templates (as :class:`bkl.model.Template` objects).

    .. attribute:: source_pos

       Source code position of template's definition, or :const:`None`.
    """
    def __init__(self, name, bases, source_pos=None):
        self.name = name
        self.bases = bases
        self.source_pos = source_pos
        # for internal use, this is a list of AST nodes that
        # define the configuration
        self._definition = []


class ModelPart(object):
    """
    Base class for model "parts", i.e. projects, modules or targets. Basically,
    anything that can have variables on it.

    .. attribute:: name

       Name of the part -- e.g. target name, filename of source file etc.

    .. attribute:: variables

       Dictionary of all variables defined in global scope in this module

    .. attribute:: parent

       Parent model part of this one, i.e. the part one step higher in object
       model hierarchy (e.g. module for a target). May only be ``None`` for
       toplevel part (the project).
       Dictionary of all variables defined in global scope in this module

    .. attribute:: source_pos

       Source code position of object's definition, or :const:`None`.
    """
    def __init__(self, parent, source_pos=None):
        self.parent = parent
        self.variables = utils.OrderedDict()
        self.source_pos = source_pos

    def _clone_into(self, clone):
        clone.source_pos = self.source_pos
        # variables must be copied, but shallow copy is OK for them
        clone.variables = utils.OrderedDict()
        for k,v in self.variables.iteritems():
            clone.variables[k] = copy.copy(v)

    def _clone(self, parent, objmap):
        raise NotImplementedError


    @property
    def project(self):
        """
        The :class:`bkl.model.Project` project this part belongs to.
        """
        prj = self
        while prj.parent is not None:
            prj = prj.parent
        assert isinstance(prj, Project)
        return prj

    @property
    def module(self):
        """
        The :class:`bkl.model.Module` that this part belongs to.
        """
        prj = self
        while not isinstance(prj, Module):
            prj = prj.parent
        return prj

    @memoized_property
    def fully_qualified_name(self):
        """
        Fully qualified name of this part. E.g. "main::submodule::mylibrary".
        """
        s = self.parent.fully_qualified_name
        return "%s::%s" % (s, self.name) if s else self.name


    def child_parts(self):
        """
        Yields model parts that are (direct) children of this.
        """
        raise NotImplementedError

    def get_child_part_by_name(self, name):
        """
        Returns child of this part of the model with given name (e.g. target
        with that name). Throws if not found.
        """
        for ch in self.child_parts():
            if ch.name == name:
                return ch
        raise error.NotFoundError("\"%s\" not found in %s" % (name, self))


    @property
    def condition(self):
        """
        Condition expression (:class:`bkl.expr.Expr`) that describes when should
        this part of the model be included. If it evaluates to true, the part is
        build, otherwise it is not.  Typical use is enabling some targets or
        source files only for some toolsets, but it may be more complicated.
        Depending on the context and the toolset, the expression may even be
        undeterminable until make-time, if it references some user options (but
        not all toolsets can handle this). Is :const:`None` if no condition is
        associated.
        """
        try:
            return self.variables["_condition"].value
        except KeyError:
            return None

    def should_build(self):
        """
        Evaluates the `condition` property on this part and returns True if it
        should be built or False otherwise. Throws NonConstError if it cannot
        be determined.
        """
        # see also ConfigurationProxy.should_build(), keep in sync!
        cond = self.condition
        if cond is None:
            return True
        try:
            return cond.as_py()
        except error.NonConstError:
            from bkl.interpreter.simplify import simplify
            cond = simplify(cond)
            raise error.CannotDetermineError("condition for building %s couldn't be resolved\n(condition \"%s\" set at %s)" %
                        (self, cond, cond.pos),
                        pos=self.source_pos)


    def get_variable(self, name):
        """
        Returns variable object for given variable or None if it is not
        defined *at this scope*.

        This method does not do any recursive resolution or account for
        properties and their default values; it merely gets the variable object
        if it is defined at this scope.

        .. seealso:: :meth:`get_variable_value()`, :meth:`resolve_variable()`
        """
        try:
            return self.variables[name]
        except KeyError:
            return None


    def resolve_variable(self, name):
        """
        Returns variable object for given variable or None if it is not
        defined.

        Unlike :meth:`get_variable()`, this method does perform recursive
        resolution and finds the variable (if it exists) according to the same
        rules that apply to `$(...)` expressions and to
        :meth:`get_variable_value()`.

        .. seealso:: :meth:`get_variable()`, :meth:`get_variable_value()`

        .. note:: Unlike :meth:`get_variable_value()`, this method doesn't
                  look for properties' default values.
        """
        var = self.get_variable(name)
        if var is not None:
            return var

        if self.parent:
            # there may be a property with this name; if so, we must check it for
            # its 'inheritable' flag:
            p = self.get_prop(name)
            can_inherit = (p is None) or p.inheritable
            if can_inherit:
                return self.parent.resolve_variable(name)
        return None


    def get_variable_value(self, name):
        """
        Similar to get_variable(), but returns the expression with variable's
        value. Throws and exception if the variable isn't defined, neither in
        this scope or in any of its parent scopes.

        If variable *name* is not explicitly defined, but a property with the
        same name exists in this scope, then its default value is used.

        If the variable is not defined in this scope at all, looks in the
        parent -- but only if *name* doesn't correspond to non-inheritable
        property. In other words, fails only if the variable isn't defined for
        use in this scope.

        Throws if the value cannot be found.

        As a shorthand syntax for this function, key indices may be used:
        >>> target["includedirs"]

        .. seealso:: :meth:`resolve_variable()`
        """
        var = self.resolve_variable(name)
        if var is not None:
            return var.value

        # there may be a property with this name; try to find it and use its
        # default value
        scope = self
        while scope:
            p = scope.get_prop(name)
            if p is not None:
                return p.default_expr(scope, throw_if_required=False)
            scope = scope.parent
        raise error.UndefinedError("unknown variable \"%s\"" % name)


    def is_variable_explicitly_set(self, name):
        """
        Returns true if the variable was set in the bakefiles explicitly.
        """
        var = self.resolve_variable(name)
        return var.is_explicitly_set if var else False

    def is_variable_null(self, name):
        """
        Returns true if the variable is unset or null (which amounts to not
        being set in this toolset / under current condition).
        """
        var = self.resolve_variable(name)
        if var is None:
            return True
        return var.value.is_null()


    def add_variable(self, var):
        """Adds a new variable object."""
        assert var.name not in self.variables
        self.variables[var.name] = var


    def set_property_value(self, prop, value):
        """
        Adds variable with a value for property *prop*.

        The property must exist on this model part. This is just a convenience
        wrapper around :meth:`add_variable()` and :meth:`get_prop()`.
        """
        if prop in self.variables:
            self.variables[prop].value = value
        else:
            v = Variable.from_property(self.get_prop(prop), value)
            self.add_variable(v)


    def get_prop(self, name):
        """
        Try to get a property *name*. Called by get_variable_value() if no
        variable with such name could be found.

        Note that unlike :meth:`get_variable()`, this one doesn't work
        recursively upwards, but finds only properties that are defined for
        this scope.

        .. seealso:: :meth:`enum_props()`
        """
        p = self._get_prop(name)
        if p is None or not p._scope_is_directly_for(self):
            return None
        else:
            return p

    def get_matching_prop_with_inheritance(self, name):
        """
        Like :meth:`get_prop()`, but looks for inheritable properties defined
        for child scopes too (e.g. returns per-target property 'outputdir' even
        in module scope).

        (This is used for assigning into variables and validating them against
        properties. Don't use unless you know what you're doing.)
        """
        return self._get_prop(name)

    def _get_prop(self, name):
        raise NotImplementedError

    def enum_props(self):
        """
        Enumerates properties defined on this object.

        Like :meth:`get_prop()`, this method doesn't work recursively upwards,
        but lists only properties that are defined for this scope.

        .. seealso:: :meth:`get_prop()`
        """
        raise NotImplementedError


    def make_variables_for_missing_props(self, toolset):
        """
        Creates variables for properties that don't have variables set yet.

        :param toolset: Name of the toolset to generate for. Properties
                specific to other toolsets are ignored for efficiency.
        """
        for p in self.enum_props():
            if p.toolsets and toolset not in p.toolsets:
                continue
            if self.is_variable_null(p.name):
                if p.inheritable and not p._scope_is_directly_for(self):
                    # don't create default for inheritable properties at higher
                    # levels than what they're defined for
                    continue
                var = Variable.from_property(p, p.default_expr(self, throw_if_required=True))
                var.is_explicitly_set = False
                logger.debug("%s: setting default of %s: %s", self, var.name, var.value)
                self.variables[p.name] = var


    def all_variables(self):
        """
        Returns iterator over all variables in the target. Works recursively,
        i.e. scans all modules and targets under this object too.
        """
        for v in self.variables.itervalues():
            yield v
        for c in self.child_parts():
            for v in c.all_variables():
                yield v


    def __getitem__(self, key):
        try:
            return self.get_variable_value(key)
        except error.UndefinedError as e:
            raise KeyError(str(e))


class Project(ModelPart):
    """
    Abstract model that completely describes state of loaded and processed
    Bakefile file(s) within the project.

    .. attribute:: modules

       List of all modules included in the project.

    .. attribute:: configurations

       All configurations defined in the project.

    .. attribute:: settings

       List of all settings included in the project.

    .. attribute:: templates

       Dictionary of all templates defined in the project.
    """

    name = "project"

    def __init__(self):
        super(Project, self).__init__(parent=None)
        self.fully_qualified_name = ""
        self.modules = []
        self.configurations = utils.OrderedDict()
        self.settings = utils.OrderedDict()
        self.templates = {}
        self._srcdir_map = {}
        self.add_configuration(Configuration("Debug",   base=None, is_debug=True))
        self.add_configuration(Configuration("Release", base=None, is_debug=False))

    def clone(self):
        """
        Makes an independent copy of the model.

        Unlike deepcopy(), this does *not* copy everything, but uses an
        appropriate mix of deep and shallow copies. For example, expressions,
        which are read-only, are copied shallowly, but variables or model
        parts, both of which can be modified in further toolset-specific
        optimizations, are copied deeply.
        """
        c = Project()
        objmap = {self:c}
        ModelPart._clone_into(self, c)
        # These must be fully cloned and they self-register:
        for x in self.settings.itervalues():
            x._clone(c, objmap)
        # We'll clone submodules recursively to preserve their parent links:
        self.top_module._clone(c, objmap)
        # These are read-only, but allow manipulating the dict for removals:
        c.configurations = self.configurations.copy()
        # These are completely read-only:
        c.templates = self.templates
        c._srcdir_map = self._srcdir_map

        # We need to process all expressions and remap ReferenceExpr.context to
        # point to the new objects. This is relatively expensive (about as much
        # as all the work above was), but unavoidable without changing the way
        # ReferenceExpr works.
        class _RewriteContext(expr.RewritingVisitor):
            def __init__(self, objmap):
                super(_RewriteContext, self).__init__()
                self.objmap = objmap
            def reference(self, e):
                return expr.ReferenceExpr(e.var, self.objmap[e.context], e.pos)

        rewr = _RewriteContext(objmap)
        for var in c.all_variables():
            var.value = rewr.visit(var.value)

        return c

    def __str__(self):
        return "the project"

    def child_parts(self):
        for x in self.modules: yield x
        for x in self.settings.itervalues(): yield x

    @property
    def top_module(self):
        """
        The toplevel module of this project.
        """
        return self.modules[0]

    def all_targets(self):
        """Returns iterator over all targets in the project."""
        for mod in self.modules:
            for t in mod.targets.itervalues():
                yield t

    def get_target(self, id):
        """Returns Target object identified by its string ID."""
        for t in self.all_targets():
            if t.name == id:
                return t
        raise error.Error("target \"%s\" doesn't exist" % id)

    def has_target(self, id):
        """Returns true if target with given name exists."""
        for t in self.all_targets():
            if t.name == id:
                return True
        return False

    def _get_prop(self, name):
        return props.get_project_prop(name)

    def enum_props(self):
        return props.enum_project_props()

    def add_configuration(self, config):
        """Adds a new configuration to the project."""
        assert config.name not in self.configurations
        self.configurations[config.name] = config

    def add_template(self, templ):
        """Adds a new template to the project."""
        assert templ.name not in self.templates
        self.templates[templ.name] = templ

    def get_srcdir(self, filename):
        try:
            return self._srcdir_map[filename]
        except KeyError:
            p = os.path.dirname(filename)
            return p if p else "."

    def set_srcdir(self, filename, srcdir):
        self._srcdir_map[filename] = srcdir


class Module(ModelPart):
    """
    Representation of single compilation unit. Corresponds to one Bakefile
    input file (either specified on command line or imported using `import`
    command; files included using `include` from other files are *not*
    represented by Module object) and typically to one generated output file.

    .. attribute:: targets

       Dictionary of all targets defined in this module

    .. attribute:: source_file

       Path to the input ``.bkl`` source file this module was created from.

    .. attribute:: srcdir

       @srcdir path effective for this module.

    .. attribute:: imports

       Set of filenames of sources imported using the 'import' keyword at this
       level.
    """
    def __init__(self, parent, source_pos):
        super(Module, self).__init__(parent, source_pos)
        self.targets = utils.OrderedDict()
        self.project.modules.append(self)
        self.imports = set()

    def _clone(self, parent, objmap):
        c = Module(parent, self.source_pos)
        objmap[self] = c
        ModelPart._clone_into(self, c)
        # These must be fully cloned and they self-register:
        for x in self.targets.itervalues():
            x._clone(c, objmap)
        for x in self.submodules:
            x._clone(c, objmap)
        # These are completely read-only:
        c.imports = self.imports
        return c

    def __str__(self):
        return "module %s" % self.source_file

    def child_parts(self):
        return self.targets.itervalues()

    @property
    def source_file(self):
        return self.source_pos.filename

    @property
    def srcdir(self):
        return self.project.get_srcdir(self.source_file)

    def srcdir_as_path(self):
        p = os.path.relpath(self.srcdir, start=self.project.top_module.srcdir)
        return expr.PathExpr([expr.LiteralExpr(x) for x in p.split(os.path.sep)],
                             anchor=expr.ANCHOR_TOP_SRCDIR)

    @memoized_property
    def name(self):
        """Name of the module. Note that this is not globally unique."""
        return os.path.splitext(os.path.basename(self.source_file))[0]

    @property
    def submodules(self):
        """Submodules of this module."""
        return (x for x in self.project.modules if x.parent is self)

    def is_submodule_of(self, module):
        """Returns True if this module is (grand-)*child of *module*."""
        m = self.parent
        while m and m is not module:
            m = m.parent
        return m is module

    def _get_prop(self, name):
        return props.get_module_prop(name)

    def enum_props(self):
        return props.enum_module_props()


class ConfigurationsPropertyMixin:
    """
    Mixin class for implementation configurations property.
    """
    @property
    def configurations(self):
        """
        Returns all configurations for this model part (e.g. a target), as
        ConfigurationProxy objects that can be used similarly to the way the
        model part object itself is. In particular, it's [] operator works the
        same.

        The proxies are intended to be used in place of targets in code that
        needs to get per-configuration values of properties.

        >>> for cfg in target.configurations:
        ...     outdir = cfg["outdir"]
        """
        prj = self.project
        cfglist = self["configurations"]
        for cname in cfglist.as_py():
            try:
                cfg = prj.configurations[cname]
            except KeyError:
                # TODO: validate the values earlier, as part of vartypes validation
                raise error.Error("configuration \"%s\" not defined" % cname, pos=cfglist.pos)
            yield ConfigurationProxy(self, cfg)


class ProxyIfResolver(expr.RewritingVisitor):
    """
    Replaces references to $(config) with value, allowing the expressions
    to be evaluated.
    """
    def __init__(self, config):
        super(ProxyIfResolver, self).__init__()
        self.mapping = {"config": config}
        self.inside_cond = 0

    def visit_cond(self, e):
        try:
            self.inside_cond += 1
            return self.visit(e)
        finally:
            self.inside_cond -= 1

    def reference(self, e):
        return self.visit(e.get_value())

    def placeholder(self, e):
        if self.inside_cond:
            try:
                return expr.LiteralExpr(self.mapping[e.var], pos=e.pos)
            except KeyError:
                pass
        return e

    def if_(self, e):
        try:
            self.inside_cond += 1
            cond = self.visit(e.cond)
            # It is safe -- desirable, even -- to remove the if expression
            # here. Either it depends on a config value, in which case this
            # proxy made it evaluate to True or False, or it depends on some
            # setting, which is an error when outputting configurations-using
            # format such as Visual Studio projects. So if the below expression
            # throws NonConstError in the latter case, that's OK.
            return self.visit(e.value_yes if cond.as_py() else e.value_no)
        finally:
            self.inside_cond -= 1


class ConfigurationProxy(object):
    """
    Proxy for accessing model part's variables as configuration-specific. All
    expressions obtained using operator[] are processed to remove conditionals
    depending on the value of "config", by substituting appropriate value
    according to the configuration name passed to proxy's constructor.

    See :meth:`bkl.model.ModelPartWithConfigurations.configurations` for more information.
    """
    def __init__(self, model, config):
        self.model = model
        self.config = config
        self._visitor = ProxyIfResolver(config.name)

    name = property(lambda self: self.config.name)
    is_debug = property(lambda self: self.config.is_debug)
    project = property(lambda self: self.model.project)

    def __getitem__(self, key):
        return self._visitor.visit(self.model[key])

    def apply_subst(self, value):
        """
        Applies the proxy's magic on given value. This is useful for when
        the proxy cannot be simply used in place of a real target. For
        example, NativeLinkedType.get_ldlibs() inspects other targets too
        and so the proxy is only partially effective.
        """
        if isinstance(value, list):
            return [self._visitor.visit(x) for x in value]
        else:
            return self._visitor.visit(value)

    def should_build(self):
        # see ModelPart.should_build()
        cond = self.model.condition
        if cond is None:
            return True
        cond = self._visitor.visit_cond(cond)
        try:
            return cond.as_py()
        except error.NonConstError:
            from bkl.interpreter.simplify import simplify
            cond = simplify(cond)
            raise error.CannotDetermineError("condition for building %s couldn't be resolved\n(condition \"%s\" set at %s)" %
                        (self.model, cond, cond.pos),
                        pos=self.model.source_pos)



class Target(ModelPart, ConfigurationsPropertyMixin):
    """
    A Bakefile target.

    Variables are typed.

    .. attribute:: name

       Name (ID) of the target. This must be unique in the entire project.

    .. attribute:: type

       Type of the target, as :class:`bkl.api.TargetType` instance.

    .. attribute:: sources

       List of source files, as SourceFile instances.

    .. attribute:: headers

       List of header files, as SourceFile instances. The difference from
       :attr:`sources` is that headers are installable and usable for
       compilation of other targets, while sources are not.
    """
    def __init__(self, parent, name, target_type, source_pos):
        super(Target, self).__init__(parent, source_pos)
        self.name = name
        self.type = target_type
        self.sources = []
        self.headers = []

        assert isinstance(parent, Module)
        assert not parent.project.has_target(name)
        parent.targets[name] = self

    def _clone(self, parent, objmap):
        c = Target(parent, self.name, self.type, self.source_pos)
        objmap[self] = c
        ModelPart._clone_into(self, c)
        # These must be fully cloned:
        c.sources = [x._clone(c, objmap) for x in self.sources]
        c.headers = [x._clone(c, objmap) for x in self.headers]
        return c

    def __str__(self):
        return 'target "%s"' % self.name

    def child_parts(self):
        for x in self.sources: yield x
        for x in self.headers: yield x

    def all_source_files(self):
        return self.child_parts()

    def _get_prop(self, name):
        return props.get_target_prop(self.type, name)

    def enum_props(self):
        return props.enum_target_props(self.type)




class SourceFile(ModelPart, ConfigurationsPropertyMixin):
    """
    Source file object.
    """
    def __init__(self, parent, filename, source_pos):
        super(SourceFile, self).__init__(parent, source_pos)
        self.set_property_value("_filename", filename)

    def _clone(self, parent, objmap):
        c = SourceFile(parent, self.filename, self.source_pos)
        objmap[self] = c
        ModelPart._clone_into(self, c)
        return c

    @property
    def filename(self):
        f = self["_filename"]
        # Most of the time the filenames are just expr.PathExpr here, but this
        # isn't necessarily the case. For now the only other case that does
        # happen in practice is a variable containing a path, so we deal just
        # with it, but we may want to use a proper visitor to handle values of
        # any type correctly here in the future.
        if isinstance(f, expr.ReferenceExpr):
            f = f.get_value()
        return f

    @memoized_property
    def name(self):
        return expr.get_model_name_from_path(self.filename)

    def __str__(self):
        return "file %s" % self.filename

    def child_parts(self):
        return []

    def _get_prop(self, name):
        # TODO: need to pass file type to it
        return props.get_file_prop(name)

    def enum_props(self):
        # TODO: need to pass file type to it
        return props.enum_file_props()



class Setting(ModelPart):
    """
    User-settable make-time configuration value.
    """
    def __init__(self, parent, name, source_pos):
        super(Setting, self).__init__(parent, source_pos)
        self.name = name
        self.project.settings[name] = self

    def _clone(self, parent, objmap):
        c = Setting(parent, self.name, self.source_pos)
        objmap[self] = c
        ModelPart._clone_into(self, c)
        return c

    def __str__(self):
        return "setting %s" % self.name

    def child_parts(self):
        return []

    def _get_prop(self, name):
        return props.get_setting_prop(name)

    def enum_props(self):
        return props.enum_setting_props()
