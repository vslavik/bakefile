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

"""
Helpers for dumping Bakefile model into human-readable form.
"""

from bkl import model, expr
from bkl.interpreter import Interpreter


def dump_project(project):
    """
    Returns string with dumped, human-readable description of 'project', which
    is an instance of bakefile.model.Project.
    """
    out = ""
    for mod in project.modules:
        out += dump_module(mod)
    return out.strip()


def dump_module(module):
    """
    Returns string with dumped, human-readable description of 'module', which
    is an instance of bakefile.model.Module.
    """
    if len(module.project.modules) > 1:
        out = "module %s {\n" % module.source_file
    else:
        out = "module {\n"

    submodules = list(module.submodules)
    if submodules:
        out += "  submodules {\n"
        for s in submodules:
            out += "    %s\n" % s.source_file
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
    def generate(self):
        print dump_project(self.model)


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


def _dump_target(target):
    out = "%s %s {\n" % (target.type.name, target.name)
    out += _indent(_dump_vars(target))
    out += "\n}"
    return out
