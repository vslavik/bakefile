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
Keep track of properties for extensions or model parts.

Also define standard, always available, properties.
"""

import expr, api
from vartypes import IdType, EnumType, ListType
from api import Property



def std_target_props():
    """Creates list of all standard target properties."""
    return [
        Property("id",
                 type=IdType(),
                 default=lambda t: expr.LiteralExpr(t.name),
                 readonly=True,
                 doc="Target's unique name (ID)."),

        Property("deps",
                 type=ListType(IdType()),
                 default=[],
                 doc="Target's dependencies (list of IDs)."),
        ]


def std_module_props():
    """Creates list of all standard module properties."""
    toolsets_enum_type = EnumType(api.Toolset.all_names())

    return [
        Property("toolsets",
                 type=ListType(toolsets_enum_type),
                 default=[],
                 doc="List of toolsets to generate makefiles/projects for."),
        ]


def std_project_props():
    """Creates list of all standard project properties."""
    toolsets_enum_type = EnumType(api.Toolset.all_names())

    return [
        Property("toolset",
                 type=toolsets_enum_type,
                 default=expr.UndeterminedExpr(),
                 readonly=True,
                 doc="The toolset makefiles or projects are being generated for. "
                     "This property is set by Bakefile and can be used for performing "
                     "toolset-specific tasks or modifications."
                 ),
        ]



def _fill_prop_dict(props):
    d = {}
    for p in props:
        d[p.name] = p
    return d


class PropertiesCache(object):
    """
    Cache of existing properties.
    """

    def __init__(self):
        self.all_targets = None
        self.modules = None
        self.project = None
        self.target_types = {}


    def get_target_prop(self, target_type, name):
        if self.all_targets is None:
            self.all_targets = _fill_prop_dict(std_target_props())
        if name in self.all_targets:
            return self.all_targets[name]
        if target_type not in self.target_types:
            props = _fill_prop_dict(target_type.all_properties())
            self.target_types[target_type] = props
        else:
            props = self.target_types[target_type]
        return props.get(name, None)


    def get_module_prop(self, name):
        if self.modules is None:
            self.modules = _fill_prop_dict(std_module_props())
        return self.modules.get(name, None)


    def get_project_prop(self, name):
        if self.project is None:
            self.project = _fill_prop_dict(std_project_props())
        return self.project.get(name, None)




cache = PropertiesCache()

def get_target_prop(target_type, name):
    """
    Returns property *name* on target level for targets of type *target_type*
    if such property exists, or :const:`None` otherwise.
    """
    return cache.get_target_prop(target_type, name)


def get_module_prop(name):
    """
    Returns property *name* on module level if such property exists, or
    :const:`None` otherwise.
    """
    return cache.get_module_prop(name)


def get_project_prop(name):
    """
    Returns property *name* on module level if such property exists, or
    :const:`None` otherwise.
    """
    return cache.get_project_prop(name)
