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
        The :class:`bkl.mode.Project` project this part belongs to.
        """
        prj = self
        while prj.parent is not None:
            prj = prj.parent
        return prj

    def child_parts(self):
        """
        Yields model parts that are (direct) children of this.
        """
        raise NotImplementedError


    def get_variable(self, name, recursively=False):
        """
        Returns variable object for given variable or None if it is not
        defined.

        :param recursively: Look for the variable recursively in the parent.
        .. seealso:: :meth:`get_variable_value()`

        .. note:: Unlike :meth:`get_variable_value()`, this method doesn't
                  look for properties' default values.
        """
        if name in self.variables:
            return self.variables[name]
        else:
            if recursively and self.parent is not None:
                return self.parent.get_variable(name, recursively)
            else:
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

        .. seealso:: :meth:`get_variable()`
        """
        var = self.get_variable(name)

        if var is not None:
            return var.value

        # there may be a property with this name (with default value):
        p = self.get_prop(name)
        if p is not None:
            if p.inheritable:
                # try to obtain the value from higher scope
                higher = self.parent
                while higher is not None:
                    var = higher.get_variable(name)
                    if var is not None:
                        return var.value
                    higher = higher.parent
                # that failed, so try default value as with non-inheritables
            return p.default_expr(self)
        else: # p is None
            # 'name' is not a property, so it can only be a user-defined
            # variable. Try to find it at a higher scope.
            if self.parent:
                return self.parent.get_variable_value(name)
            else:
                raise error.UndefinedError("unknown variable \"%s\"" % name)


    def add_variable(self, var):
        """Adds a new variable object."""
        assert var.name not in self.variables
        self.variables[var.name] = var


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
            if self.get_variable(p.name, recursively=p.inheritable) is None:
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

    .. attribute: all_targets

       Dictionary of all targets in the entire project.
    """
    def __init__(self):
        super(Project, self).__init__(parent=None)
        self.modules = []
        self.all_targets = {}

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

    def get_target(self, id):
        """Returns Target object identified by its string ID."""
        try:
            return self.all_targets[id]
        except KeyError:
            raise error.Error("target \"%s\" doesn't exist" % id)

    def get_prop(self, name):
        return props.get_project_prop(name)

    def enum_props(self):
        return props.enum_project_props()


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

    def add_target(self, target):
        """Adds a new target object to this module."""
        assert target.name not in self.targets
        assert target.name not in self.project.all_targets
        self.targets[target.name] = target
        self.project.all_targets[target.name] = target

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

    def __str__(self):
        return 'target "%s"' % self.name

    def child_parts(self):
        for x in self.sources: yield x
        for x in self.headers: yield x

    def get_prop(self, name):
        return props.get_target_prop(self.type, name)

    def enum_props(self):
        return props.enum_target_props(self.type)


class SourceFile(ModelPart):
    """
    Source file object.
    """
    def __init__(self, parent, filename, source_pos):
        super(SourceFile, self).__init__(parent, source_pos)
        fn = Variable.from_property(self.get_prop("filename"), filename)
        self.add_variable(fn)

    @property
    def filename(self):
        return self["filename"]

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
