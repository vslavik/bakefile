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

from bakefile import model

def dump_model(model):
    """
    Returns string with dumped, human-readable description of 'model', which
    is an instance of bakefile.model.Model.
    """
    out = ""
    for mk in model.makefiles:
        out += "makefile {\n%s}\n" % _dump_makefile(mk)
    return out.strip()


def _dump_makefile(makefile):
    out = ""

    out += "  variables {\n"
    keys = list(makefile.variables.iterkeys())
    keys.sort()
    for name in keys:
        out += "    %s\n" % _dump_variable(makefile.variables[name])
    out +=  "  }\n"

    out += "  targets {\n"
    keys = list(makefile.targets.iterkeys())
    keys.sort()
    for name in keys:
        out += "    %s\n" % _dump_target(makefile.targets[name])
    out +=  "  }\n"

    return out


def _dump_variable(var):
    return "%s = %s" % (var.name, _dump_expression(var.value))


def _dump_target(target):
    return "%s %s" % (target.type.name, target.name)


def _dump_expression(expr):
    if isinstance(expr, model.ConstExpr):
        # FIXME: handle types
        return '"%s"' % expr.value
    if isinstance(expr, model.ListExpr):
        items = [_dump_expression(e) for e in expr.items]
        return "[%s]" % ", ".join(items)
    else:
        assert False, "unknown expression type"
