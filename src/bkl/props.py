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

"""
Keep track of properties for extensions or model parts.

Also define standard, always available, properties.
"""

import expr, api, utils
from vartypes import IdType, EnumType, ListType, PathType, StringType, BoolType, TheAnyType
from api import Property

def _std_model_part_props():
    return [
        Property("_condition",
             type=BoolType(),
             default=True,
             readonly=True,
             inheritable=False,
             doc="""
                 Whether to include this object in the build.
                 Typically a more complicated boolean expression.
                 """),
        ]

def std_file_props():
    """Creates list of all standard source file properties."""
    return _std_model_part_props() + [
        Property("_filename",
             type=PathType(),
             default=[],
             readonly=True,
             inheritable=False,
             doc="Source file name."),
        Property("compile-commands",
             type=ListType(StringType()),
             default=[],
             inheritable=False,
             doc="""
                 Command or commands to run to compile this source file,
                 i.e. to generate other file(s) from it. This can be used for
                 generating some files or for compiling custom file types.

                 Two placeholders can be used in the commands, ``%(in)`` and
                 ``%(out)``. They are replaced with the name of the source file
                 and ``outputs`` respectively. Both placeholders are optional.
                 """),
        Property("compile-message",
             type=StringType(),
             default=expr.NullExpr(),
             inheritable=False,
             doc="""
                 Message shown to the user when running the command.

                 The same placeholder as in *compiler-commands* can be used.
                 """),
        Property("outputs",
             type=ListType(PathType()),
             default=lambda t: None if t["compile-commands"] else expr.NullExpr(),
             inheritable=False,
             doc="""
                 Output files created by the build step that compiles this file

                 Only applicable if *compile-commands* is set.
                 """),
        Property("dependencies",
             type=ListType(PathType()),
             default=[],
             inheritable=False,
             doc="""
                 List of additional files that the source file or or its
                 commands depend on.

                 List any files that must be created before the source file is
                 compiled, such as generated header files. If *compile-commands*
                 is set, list any other files referenced by the commands.
                 """),
        ]


def std_target_props():
    """Creates list of all standard target properties."""
    return _std_model_part_props() + [
        Property("id",
                 type=IdType(),
                 default=lambda t: expr.LiteralExpr(t.name),
                 readonly=True,
                 inheritable=False,
                 doc="Target's unique name (ID)."),

        Property("deps",
                 type=ListType(IdType()),
                 default=[],
                 inheritable=False,
                 doc="""
                     Dependencies of the target (list of IDs).

                     The dependencies are handled in target-specific ways.
                     At the very least, they are added to the list of
                     dependencies in generated makefiles or projects to ensure
                     correct build order. Some targets may be smart about some
                     kinds of the dependencies and do more.

                     In particular, compiled targets (executables, DLLs) will
                     automatically link against all libraries found in `deps`.
                     """),

        Property("pre-build-commands",
                 type=ListType(StringType()),
                 default=[],
                 inheritable=False,
                 doc="""
                     Custom commands to run before building the target.

                     The value is a list of shell commands to run.  Notice that
                     the commands are platform-specific and so typically need
                     to be set conditionally depending on the value of
                     ``toolset``.

                     Currently only implemented by Visual Studio.
                     """),
        Property("post-build-commands",
                 type=ListType(StringType()),
                 default=[],
                 inheritable=False,
                 doc="""
                     Custom commands to run after building the target.

                     The value is a list of shell commands to run.  Notice that
                     the commands are platform-specific and so typically need
                     to be set conditionally depending on the value of
                     ``toolset``.

                     Currently only implemented by Visual Studio.
                     """),

        Property("configurations",
                 type=ListType(StringType()), # FIXME: use a custom type that validates config names
                 default="Debug Release",
                 inheritable=True,
                 doc="""
                     List of configurations to use for this target.

                     See :ref:`configurations` for more information.
                     """
                 ),
        ]


def std_module_props():
    """Creates list of all standard module properties."""
    toolsets_enum_type = EnumType("toolset", sorted(api.Toolset.all_names()))

    return [
        Property("toolsets",
                 type=ListType(toolsets_enum_type),
                 default=[],
                 inheritable=True,
                 doc="List of toolsets to generate makefiles/projects for."),
        Property("_srcdir",
             type=PathType(),
             default=lambda x: x.srcdir_as_path(),
             readonly=True,
             inheritable=False,
             doc="The value of @srcdir anchor for the module."),
        ]


def std_project_props():
    """Creates list of all standard project properties."""
    toolsets_enum_type = EnumType("toolset", sorted(api.Toolset.all_names()))

    return [
        Property("toolset",
                 type=toolsets_enum_type,
                 default=expr.PlaceholderExpr("toolset"),
                 readonly=True,
                 inheritable=False,
                 doc="The toolset makefiles or projects are being generated for. "
                     "This property is set by Bakefile and can be used for performing "
                     "toolset-specific tasks or modifications."
                 ),
        Property("config",
                 type=StringType(),
                 default=expr.PlaceholderExpr("config"),
                 readonly=True,
                 inheritable=False,
                 doc="""
                     Current configuration.

                     This property is set by Bakefile and can be used for performing
                     per-configuration modifications. The value is one of the
                     *configurations* values specified for the target.

                     See :ref:`configurations` for more information.
                     """
                 ),
        Property("arch",
                 type=StringType(),
                 default=expr.PlaceholderExpr("arch"),
                 readonly=True,
                 inheritable=False,
                 doc="""
                     Current architecture.

                     This property is set by Bakefile and can be used for
                     performing per-architecture modifications (if the toolset
                     supports it, which currently only Visual Studio does).
                     The value is one of the *archs* values specified for the
                     target.
                     """
                 ),
        ]


def std_setting_props():
    """Creates list of all standard Setting properties."""
    return _std_model_part_props() + [
        Property("help",
                 type=StringType(),
                 default=expr.NullExpr(),
                 inheritable=False,
                 doc="""
                     Documentation for the setting.
                     This will be used in the generated output to explain the setting to
                     the user, if supported by the toolset.
                     """
                 ),
        Property("default",
                 type=TheAnyType,
                 default=expr.NullExpr(),
                 inheritable=False,
                 doc="Default value of the setting, if any."
                 ),
        ]


class PropertiesDict(utils.OrderedDict):
    """
    Dictionary of properties, keyed by their names.
    """
    def __init__(self, scope):
        super(PropertiesDict, self).__init__()
        self.scope = scope

    def add(self, prop, as_inherited=False):
        if prop.name in self:
            # The same property may be shared by different target types (e.g.
            # "defines" for any native compiled target: programs, shared or
            # static libraries, ...).
            # That is OK, the property comes from a common base class then and
            # is the same instance. Having two different properties with the
            # same name is not OK, though.
            if self[prop.name] is not prop:
                raise RuntimeError("property \"%s\" defined more than once at the same scope (%s)" %
                                   (prop.name, self.scope))

        if as_inherited:
            assert prop.scopes # must have assigned scope from elsewhere already
        else:
            prop._add_scope(self.scope)
        self[prop.name] = prop

def _fill_prop_dict(props, scope):
    d = PropertiesDict(scope)
    for p in props:
        d.add(p)
    return d

def _propagate_inheritables(props, into):
    """
    Add inheritable properties from *props* into *into* dictionary, which holds
    properties for a higher-level scope.
    """
    for p in props.itervalues():
        if p.inheritable:
            into.add(p, as_inherited=True)

def _collect_properties_from_others(variable_name):
    """
    Yields properties from "external" source -- i.e. not defined on the model
    part type (e.g. target type) itself, but in toolset.
    """
    for toolset in api.Toolset.all():
        for p in toolset.all_properties(variable_name):
            p._add_toolset(toolset.name)
            yield p
    for step in api.CustomStep.all():
        for p in step.all_properties(variable_name):
            yield p


class PropertiesRegistry(object):
    """
    Registry of existing properties.
    """
    def __init__(self):
        self._init_vars()

    def _init_vars(self):
        self._initialized = False
        self.all_targets = None
        self.all_files = None
        self.modules = None
        self.project = None
        self.settings = None
        self.target_types = {}

    def get_project_prop(self, name):
        """
        Returns property *name* on module level if such property exists, or
        :const:`None` otherwise.
        """
        if not self._initialized:
            self._init_props()
        return self.project.get(name, None)

    def get_module_prop(self, name):
        """
        Returns property *name* on module level if such property exists, or
        :const:`None` otherwise.
        """
        if not self._initialized:
            self._init_props()
        return self.modules.get(name, None)

    def get_target_prop(self, target_type, name):
        """
        Returns property *name* on target level for targets of type *target_type*
        if such property exists, or :const:`None` otherwise.
        """
        if not self._initialized:
            self._init_props()
        if name in self.all_targets:
            return self.all_targets[name]
        else:
            return self.target_types[target_type].get(name, None)

    def get_file_prop(self, name):
        """
        Returns property *name* on source file level if such property exists, or
        :const:`None` otherwise.
        """
        if not self._initialized:
            self._init_props()
        return self.all_files.get(name, None)

    def get_setting_prop(self, name):
        """
        Returns property *name* of a Setting object if such property exists, or
        :const:`None` otherwise.
        """
        if not self._initialized:
            self._init_props()
        return self.settings.get(name, None)

    def enum_project_props(self):
        if not self._initialized:
            self._init_props()
        for p in self.project.itervalues():
            yield p

    def enum_module_props(self):
        if not self._initialized:
            self._init_props()
        for p in self.modules.itervalues():
            yield p

    def enum_target_props(self, target_type):
        if not self._initialized:
            self._init_props()
        for p in self.target_types[target_type].itervalues():
            yield p
        for p in self.all_targets.itervalues():
            yield p

    def enum_file_props(self):
        if not self._initialized:
            self._init_props()
        for p in self.all_files.itervalues():
            yield p

    def enum_setting_props(self):
        if not self._initialized:
            self._init_props()
        for p in self.settings.itervalues():
            yield p

    def _init_props(self):
        assert not self._initialized

        # Project:
        self.project = _fill_prop_dict(std_project_props(), api.Property.SCOPE_PROJECT)
        for p in _collect_properties_from_others("properties_project"):
            self.project.add(p)

        # Modules:
        self.modules = _fill_prop_dict(std_module_props(), api.Property.SCOPE_MODULE)
        for p in _collect_properties_from_others("properties_module"):
            self.modules.add(p)

        # All targets:
        self.all_targets = _fill_prop_dict(std_target_props(), api.Property.SCOPE_TARGET)
        for p in _collect_properties_from_others("properties_target"):
            self.all_targets.add(p)
        _propagate_inheritables(self.all_targets, self.modules)

        # Specific target types:
        for target_type in api.TargetType.all():
            props = _fill_prop_dict(target_type.all_properties(), target_type.name)
            for p in _collect_properties_from_others("properties_%s" % target_type):
                props.add(p)
            self.target_types[target_type] = props
            _propagate_inheritables(props, self.modules)

        # File types:
        self.all_files = _fill_prop_dict(std_file_props(), api.Property.SCOPE_FILE)
        for p in _collect_properties_from_others("properties_file"):
            self.all_files.add(p)
        _propagate_inheritables(self.all_files, self.all_targets)
        _propagate_inheritables(self.all_files, self.modules)

        # Settings:
        self.settings = _fill_prop_dict(std_setting_props(), api.Property.SCOPE_SETTING)
        for p in _collect_properties_from_others("properties_setting"):
            self.settings.add(p)

        self._initialized = True

    def force_rescan(self):
        """Force re-scanning of properties"""
        self._init_vars()


registry = PropertiesRegistry()

get_project_prop = registry.get_project_prop
get_module_prop = registry.get_module_prop
get_target_prop = registry.get_target_prop
get_file_prop = registry.get_file_prop
get_setting_prop = registry.get_setting_prop

enum_project_props = registry.enum_project_props
enum_module_props = registry.enum_module_props
enum_target_props = registry.enum_target_props
enum_file_props = registry.enum_file_props
enum_setting_props = registry.enum_setting_props
