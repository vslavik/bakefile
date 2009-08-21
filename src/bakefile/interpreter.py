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

import api
import model
from parser.ast import *
from error import ParserError

class Interpreter(object):
    """
    Interpreter processes parsed AST and constructs a project model from it.

    It doesn't do anything smart like optimizing things, it does only the
    minimal processing needed to produce a valid model. This includes checking
    variables scopes etc.
    """

    def __init__(self, ast):
        """Creates interpreter for given AST."""
        self.ast = ast
        self._ast_dispatch = {
            AssignmentNode : self.on_assignment,
            TargetNode     : self.on_target,
        }


    def create_model(self):
        """Returns constructed model, as model.Project instance."""
        self.model = model.Project()
        self.context = model.Module()
        self.model.modules.append(self.context)

        for n in self.ast.children:
            self._handle_node(n)

        return self.model


    def _handle_node(self, node):
        func = self._ast_dispatch[type(node)]
        func(node)


    def on_assignment(self, node):
        var = self.context.get_variable(node.var.text)
        assert not var # FIXME: implement changing variable too, with typecheck
        if not var:
            var = model.Variable(node.var.text,
                                 self._build_assigned_value(node.value))
            self.context.add_variable(var)


    def on_target(self, node):
        name = node.name.text
        type_name = node.type.text
        try:
            type = api.TargetType.get(type_name)
            target = model.Target(name, type)
            self.context.add_target(target)
        except KeyError:
            # FIXME: include location information
            raise ParserError(node.pos, "unknown target type \"%s\"" % type_name)


    def _build_assigned_value(self, ast, result_type=None):
        """
        Build model.Expr from given AST node of AssignedValueNode type.

        If result_type is specified, then the expression will be of that
        type, or the function will throw an exception.
        """
        assert isinstance(ast, AssignedValueNode)
        values = ast.values
        if len(values) == 1:
            return self._build_expression(values[0], result_type)
        else:
            assert result_type==None # FIXME: handle nested type correctly
            items = [self._build_expression(e, result_type) for e in values]
            return model.ListExpr(items)


    def _build_expression(self, ast, result_type=None):
        if isinstance(ast, ValueNode):
            # FIXME: type handling
            return model.ConstExpr(ast.text)
        assert False, "unrecognized AST node"
