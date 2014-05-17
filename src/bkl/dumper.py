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

"""
Helpers for dumping Bakefile model into human-readable form.
"""

from bkl.interpreter import Interpreter


def dump_project(project):
    """
    Returns string with dumped, human-readable description of 'project', which
    is an instance of bakefile.model.Project.
    """
    out = ""
    for s in project.settings.itervalues():
        out += _dump_setting(s)
    if project.variables:
        out += "variables {\n"
        out += _indent(_dump_vars(project))
        out += "}\n"
    for mod in project.modules:
        out += dump_module(mod)
    return out.strip()


def dump_module(module):
    """
    Returns string with dumped, human-readable description of 'module', which
    is an instance of bakefile.model.Module.
    """
    if len(module.project.modules) > 1:
        # use Unix filename syntax in the dumps even on Windows
        out = "module %s {\n" % module.fully_qualified_name
    else:
        out = "module {\n"

    submodules = list(module.submodules)
    if submodules:
        out += "  submodules {\n"
        for s in submodules:
            # use Unix filename syntax in the dumps even on Windows
            filename = s.source_file.replace("\\", "/")
            out += "    %s\n" % filename
        out += "  }\n"

    out += "  variables {\n"
    out += _indent(_dump_vars(module))
    out += "  }\n"

    out += "  targets {\n"
    for name in module.targets.iterkeys():
        out += _indent(_indent(_dump_target(module.targets[name])))
    out +=  "  }\n}\n\n"

    return out


class DumpingInterpreter(Interpreter):
    def __init__(self, toolset=None):
        super(DumpingInterpreter, self).__init__()
        self.toolset = toolset

    def generate(self):
        if self.toolset:
            model = self.make_toolset_specific_model(self.toolset)
            self.finalize_for_toolset(model, self.toolset)
        else:
            model = self.model
        print dump_project(model)


def _indent(text):
    lines = text.split("\n")
    out = ""
    for x in lines:
        if x != "":
            x = "  %s" % x
            out += "%s\n" % x
    return out


def _dump_vars(part):
    out = ""
    for name in part.variables.iterkeys():
        out += "  %s\n" % _dump_variable(part.variables[name])
    return out


def _dump_variable(var):
    return "%s = %s" % (var.name, var.value)


def _dump_source(source):
    out = str(source)
    vars = [x for x in source.variables.iterkeys() if x != "_filename"]
    if vars:
        out += "\t{ "
        out += "; ".join(_dump_variable(source.variables[name]) for name in vars)
        out += " }"
    return out


def _dump_target(target):
    out = "%s %s {\n" % (target.type.name, target.name)
    out += _dump_vars(target)
    out_files=""
    if target.sources:
        out_files += "sources {\n"
        out_files += _indent("\n".join(_dump_source(s) for s in target.sources))
        out_files += "\n}\n"
    if target.headers:
        out_files += "headers {\n"
        out_files += _indent("\n".join(_dump_source(s) for s in target.headers))
        out_files += "\n}\n"
    if out_files:
        out += _indent(out_files)
    out += "}"
    return out


def _dump_setting(setting):
    out = "setting %s {\n" % setting.name
    out += _dump_vars(setting)
    out += "}\n"
    return out
