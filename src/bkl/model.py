#
#  This file is part of Bakefile (http://www.bakefile.org)
#
#  Copyright (C) 2008-2009 Vaclav Slavik
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

import error, expr, vartypes, utils


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


    def set_value(self, value):
        """
        Sets new value on the variable. The new value must have same type
        as current value. Read-only variable cannot be set.

        :param value: New value as :class:`bkl.expr.Expr` object.
        """
        assert not self.readonly
        # FIXME: type checks
        self.value = value



class ModelPart(object):
    """
    Base class for model "parts", i.e. projects, modules or targets. Basically,
    anything that can have variables on it.

    .. attribute:: variables

       Dictionary of all variables defined in global scope in this module
    """

    def __init__(self):
        self.variables = utils.OrderedDict()


    def _init_from_properties(self, props_source):
        """
        Creates variables for properties with default values. Properties are
        taken from a "type" object (e.g. :class:`bkl.api.TargetType` or
        :class:`bkl.api.Toolset`). This object must have *class* member variable
        var:`properties` with a list of :class:`bkl.api.Property` instances
        (base class' properties are automagically scanned too).

        :param type: Object with the properties definition.

        .. seealso:: :class:`bkl.api.TargetType`
        """
        t = type(props_source)
        prev_props = None
        while "properties" in dir(t):
            if t.properties is not prev_props:
                prev_props = t.properties
                for p in t.properties:
                    self.add_variable(Variable(p.name,
                                               value=p.default_expr(self),
                                               readonly=p.readonly))
            # else:
            #   derived class didn't define properties of its own and we don't
            #   want to add the same properties twice
            t = t.__base__


    def get_variable(self, name):
        """
        Returns variable object for given variable or None if it is not
        defined.
        """
        # FIXME: implement recursive lookup
        if name in self.variables:
            return self.variables[name]
        else:
            return None


    def get_variable_value(self, name):
        """
        Similar to get_variable(), but returns the expression with variable's
        value. Throws and exception if the variable isn't defined.
        """
        var = self.get_variable(name)
        if not var:
            raise error.Error(None, "unknown variable \"%s\"" % name)
        return var.value


    def add_variable(self, var):
        """Adds a new variable object."""
        assert var.name not in self.variables
        self.variables[var.name] = var



class Project(ModelPart):
    """
    Abstract model that completely describes state of loaded and processed
    Bakefile file(s) within the project.

    .. attribute: modules

       List of all modules included in the project.
    """
    def __init__(self):
        super(Project, self).__init__()
        self.modules = []



class Module(ModelPart):
    """
    Representation of single compilation unit. Corresponds to one Bakefile
    input file (either specified on command line or imported using `import`
    command; files included using `include` from other files are *not*
    represented by Module object) and typically to one generated output file.

    .. attribute:: targets

       Dictionary of all targets defined in this module
    """

    def __init__(self):
        super(Module, self).__init__()
        self.targets = utils.OrderedDict()


    def add_target(self, target):
        """Adds a new target object."""
        assert target.name not in self.targets
        self.targets[target.name] = target



class Target(ModelPart):
    """
    A Bakefile target.

    Variables are typed.

    .. attribute:: name

       Name (ID) of the target. This must be unique in the entire project.

    .. attribute:: target_type

       Type of the target, as :class:`bkl.api.TargetType` instance.
    """

    def __init__(self, name, target_type):
        super(Target, self).__init__()
        self.name = name
        self.type = target_type
        self._init_from_properties(target_type)
