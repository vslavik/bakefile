#
#  This file is part of Bakefile (http://www.bakefile.org)
#
#  Copyright (C) 2008-2012 Vaclav Slavik
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

import logging
logger = logging.getLogger("bkl.model")

import error, vartypes, utils
import props
import expr

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
    """
    def __init__(self, name, value, type=None, readonly=False):
        self.name = name
        if type is None:
            type = vartypes.guess_expr_type(value)
        self.type = type
        self.value = value
        self.readonly = readonly
        self.is_property = False

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

    def clone(self, new_name, source_pos=None):
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


class ModelPart(object):
    """
    Base class for model "parts", i.e. projects, modules or targets. Basically,
    anything that can have variables on it.

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

    def child_parts(self):
        """
        Yields model parts that are (direct) children of this.
        """
        raise NotImplementedError


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
                return p.default_expr(self)
            scope = scope.parent
        raise error.UndefinedError("unknown variable \"%s\"" % name)


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
            if self.resolve_variable(p.name) is None:
                if p.inheritable and not p._scope_is_for(self):
                    # don't create default for inheritable properties at higher
                    # levels than what they're defined for
                    continue
                var = Variable.from_property(p, p.default_expr(self))
                self.add_variable(var)
                logger.debug("%s: setting default of %s: %s", self, var.name, var.value)


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

    .. attribute: modules

       List of all modules included in the project.

    .. attribute: configurations

       All configurations defined in the project.
    """
    def __init__(self):
        super(Project, self).__init__(parent=None)
        self.modules = []
        self.configurations = utils.OrderedDict()
        self.add_configuration(Configuration("Debug",   base=None, is_debug=True))
        self.add_configuration(Configuration("Release", base=None, is_debug=False))

    def __str__(self):
        return "the project"

    def child_parts(self):
        return self.modules

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

    def get_prop(self, name):
        return props.get_project_prop(name)

    def enum_props(self):
        return props.enum_project_props()

    def add_configuration(self, config):
        """Adds a new configuration to the project."""
        assert config.name not in self.configurations
        self.configurations[config.name] = config


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
    """
    def __init__(self, parent, source_pos):
        super(Module, self).__init__(parent, source_pos)
        self.targets = utils.OrderedDict()
        self.project.modules.append(self)

    def __str__(self):
        return "module %s" % self.source_file

    def child_parts(self):
        return self.targets.itervalues()

    @property
    def source_file(self):
        return self.source_pos.filename

    @property
    def name(self):
        """Name of the module"""
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

    def get_prop(self, name):
        return props.get_module_prop(name)

    def enum_props(self):
        return props.enum_module_props()


class Target(ModelPart):
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

    def __str__(self):
        return 'target "%s"' % self.name

    def child_parts(self):
        for x in self.sources: yield x
        for x in self.headers: yield x

    def get_prop(self, name):
        return props.get_target_prop(self.type, name)

    def enum_props(self):
        return props.enum_target_props(self.type)

    @property
    def configurations(self):
        """
        Returns all configurations for this target, as ConfigurationProxy
        objects that can be used similarly to the way the target object
        itself is. In particular, it's [] operator works the same.

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


class _ProxyIfResolver(expr.RewritingVisitor):
    """
    Replaces references to $(config) with value, allowing the expressions
    to be evaluated.
    """
    def __init__(self, config):
        self.config = config
        self.inside_cond = 0

    def reference(self, e):
        return self.visit(e.get_value())

    def placeholder(self, e):
        if self.inside_cond and e.var == "config":
            return expr.LiteralExpr(self.config, pos=e.pos)
        else:
            return e

    def if_(self, e):
        try:
            self.inside_cond += 1
            cond = self.visit(e.cond)
        finally:
            self.inside_cond -= 1
        yes = self.visit(e.value_yes)
        no = self.visit(e.value_no)
        return expr.IfExpr(cond, yes, no, pos=e.pos)


class ConfigurationProxy(object):
    """
    Proxy for accessing model part's variables as configuration-specific. All
    expressions obtained using operator[] are processed to remove conditionals
    depending on the value of "config", by substituting appropriate value
    according to the configuration name passed to proxy's constructor.

    See :meth:`bkl.model.Target.configurations` for more information.
    """
    def __init__(self, model, config):
        self.config = config
        self.name = config.name
        self.is_debug = config.is_debug
        self.model = model
        self._visitor = _ProxyIfResolver(config.name)

    def __getitem__(self, key):
        return self._visitor.visit(self.model[key])


class SourceFile(ModelPart):
    """
    Source file object.
    """
    def __init__(self, parent, filename, source_pos):
        super(SourceFile, self).__init__(parent, source_pos)
        self.set_property_value("_filename", filename)

    @property
    def filename(self):
        return self["_filename"]

    def __str__(self):
        return "file %s" % self.filename

    def child_parts(self):
        return []

    def get_prop(self, name):
        # TODO: need to pass file type to it
        return props.get_file_prop(name)

    def enum_props(self):
        # TODO: need to pass file type to it
        return props.enum_file_props()
