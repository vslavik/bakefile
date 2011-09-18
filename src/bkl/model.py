#
#  This file is part of Bakefile (http://www.bakefile.org)
#
#  Copyright (C) 2008-2011 Vaclav Slavik
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

import copy
import types

import error, expr, vartypes, utils
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
    """
    def __init__(self, name, value, type=vartypes.AnyType(), readonly=False):
        self.name = name
        self.type = type
        self.value = value
        self.readonly = readonly

    @staticmethod
    def from_property(prop, value):
        """
        Creates a variable from property *prop*. In particular, takes the type
        and :attr:`readonly` attribute from the property. Properties' default
        value is *not* assigned; *value* is used instead.
        """
        v = Variable(name=prop.name,
                     value=None,
                     type=prop.type,
                     readonly=prop.readonly)
        # this is intentional; if the property is read-only,
        # set_value() will fail:
        v.set_value(value)
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
    """
    def __init__(self, parent):
        self.parent = parent
        self.variables = utils.OrderedDict()

    # This is needed to make deepcopy work: it doesn't like neither cyclic
    # references (self.parent) nor weakrefs. So we exclude self.parent from
    # pickling and deepcopy -- it is added back by Project.__deepcopy__.
    def __getstate__(self):
        return dict(x for x in self.__dict__.iteritems() if x[0] != "parent")


    def get_variable(self, name):
        """
        Returns variable object for given variable or None if it is not
        defined. If the variable is not defined in this scope, looks in the
        parent. In other words, None is returned only if the variable isn't
        defined anywhere.

        .. seealso:: :meth:`get_variable_value()`

        .. note:: Unlike :meth:`get_variable_value()`, this method doesn't
                  look for properties' default values.
        """
        if name in self.variables:
            return self.variables[name]
        else:
            if self.parent:
                return self.parent.get_variable(name)
            else:
                return None


    def get_variable_value(self, name):
        """
        Similar to get_variable(), but returns the expression with variable's
        value. Throws and exception if the variable isn't defined, neither in
        this scope or in any of its parent scopes.

        If variable *name* is not explicitly defined in the model, but a
        property with the same name exists in this scope, then its default
        value is used.

        .. seealso:: :meth:`get_variable()`
        """
        var = self.get_variable(name)

        if var is not None:
            return var.value

        # else, as last bet, try to find a property with this name
        scope = self
        while scope:
            p = scope.get_prop(name)
            if p is not None:
                return p.default_expr(scope)
            scope = scope.parent
        raise error.Error("unknown variable \"%s\"" % name)


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
        """
        raise NotImplementedError


class Project(ModelPart):
    """
    Abstract model that completely describes state of loaded and processed
    Bakefile file(s) within the project.

    .. attribute: modules

       List of all modules included in the project.
    """
    def __init__(self):
        super(Project, self).__init__(parent=None)
        self.modules = []

    def __deepcopy__(self, memo):
        c = Project()
        c.variables = copy.deepcopy(self.variables, memo)
        c.modules = copy.deepcopy(self.modules, memo)
        for m in c.modules:
            m.parent = c
            for t in m.targets.itervalues():
                t.parent = m
        return c

    def __str__(self):
        return "the project"

    def all_variables(self):
        """
        Returns iterator over all variables in the project. Works recursively,
        i.e. scans all modules and targets under this object too.
        """
        for v in self.variables.itervalues():
            yield v
        for m in self.modules:
            for v in m.variables.itervalues():
                yield v
            for t in m.targets.itervalues():
                for v in t.variables.itervalues():
                    yield v

    def get_prop(self, name):
        return props.get_project_prop(name)


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
    def __init__(self, parent, source_file):
        super(Module, self).__init__(parent)
        self.targets = utils.OrderedDict()
        self.source_file = source_file

    def __str__(self):
        return "module %s" % self.source_file

    def add_target(self, target):
        """Adds a new target object."""
        assert target.name not in self.targets
        self.targets[target.name] = target

    def get_target(self, id):
        """Returns Target object identified by its string ID."""
        return self.targets[id]

    def get_prop(self, name):
        return props.get_module_prop(name)


class Target(ModelPart):
    """
    A Bakefile target.

    Variables are typed.

    .. attribute:: name

       Name (ID) of the target. This must be unique in the entire project.

    .. attribute:: target_type

       Type of the target, as :class:`bkl.api.TargetType` instance.
    """
    def __init__(self, parent, name, target_type):
        super(Target, self).__init__(parent)
        self.name = name
        self.type = target_type

    def __str__(self):
        return 'target "%s"' % self.name

    def get_prop(self, name):
        return props.get_target_prop(self.type, name)
