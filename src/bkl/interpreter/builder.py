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

from ..api import TargetType
from ..expr import *
from ..model import Module, Target, Variable
from ..parser.ast import *
from ..error import Error, ParserError
from ..vartypes import ListType
import bkl.parser.BakefileParser as BakefileParser


class Builder(object):
    """
    interpreter.Builder processes parsed AST and builds a project model
    from it.

    It doesn't do anything smart like optimizing things, it does only the
    minimal processing needed to produce a valid, albeit suboptimal, model.

    This includes checking variables scopes etc., but does *not* involve
    checks for type correctness. Passes further in the
    :class:`bkl.interpreter.Interpreter` pipeline handle that.

    .. attribute:: context

       Current context. This is the inner-most :class:`bkl.model.ModelPart`
       at the time of parsing. Initially, it is set to a new
       :class:`bkl.model.Module` instance by :meth:`create_model`. When
       descending into a target, it is temporarily set to said target and
       then restored and so on.
    """

    active_if_cond = property(lambda self: self.if_stack[-1] if self.if_stack else None,
                              doc="Currently active 'if' statement condition, if any.")

    def __init__(self):
        self.context = None
        self.if_stack = []


    def create_model(self, ast, parent):
        """Returns constructed model, as :class:`bkl.model.Module` instance."""
        mod = Module(parent, source_file=ast.filename)
        self.context = mod

        self.handle_children(ast.children, self.context)
        assert self.context is mod

        return mod


    def create_expression(self, ast, parent):
        """Creates :class:`bkl.epxr.Expr` expression in given parent's context."""
        self.context = parent
        return self._build_expression(ast)


    def handle_children(self, children, context):
        """
        Runs model creation of all children nodes.

        :param children: List of AST nodes to treat as children.
        :param context:  Context (aka "local scope"). Interpreter's
               :attr:`context` is set to it for the duration of the call.
        """
        try:
            old_ctxt = self.context
            self.context = context
            for n in children:
                self._handle_node(n)
        finally:
            self.context = old_ctxt


    def _handle_node(self, node):
        func = self._ast_dispatch[type(node)]
        try:
            func(self, node)
        except Error as e:
            # Assign position to the error if it wasn't done already; it's
            # often more convenient to do it here than to keep track of the
            # position across a hierarchy of nested calls.
            if e.pos is None and node.pos is not None:
                e.pos = node.pos
            raise e


    def on_assignment(self, node):
        varname = node.var
        append = node.append
        value = self._build_expression(node.value)
        var = self.context.get_variable(varname)

        has_cond = self.active_if_cond is not None
        if has_cond:
            if append and isinstance(value, ListExpr):
                # If conditionally appending more items to an existing list,
                # it's better to associate the condition with individual items.
                ifs = [IfExpr(self.active_if_cond,
                              yes=i,
                              no=NullExpr(),
                              pos=i.pos)
                       for i in value.items]
                value = ListExpr(ifs, pos=value.pos)
            else:
                # But when just setting the value, keep it all together as
                # a single value inside single IfExpr.
                value = IfExpr(self.active_if_cond,
                               yes=value,
                               no=NullExpr(),
                               pos=node.pos)

        if var is None:
            # If there's an appropriate property with the same name, then
            # this assignment expression needs to be interpreted as assignment
            # to said property. In other words, the new variable's type
            # must much that of the property.
            prop = self.context.get_prop(varname)
            if prop:
                if append or has_cond:
                    propval = prop.default_expr(self.context)
                else:
                    propval = NullExpr() # we'll set it below
                var = Variable.from_property(prop, propval)
                self.context.add_variable(var)

        if var is None:
            if append:
                raise ParserError('unknown variable "%s"' % varname)
            # Create new variable.
            self.context.add_variable(Variable(varname, value))
        else:
            # modify existing variable
            if append:
                if not isinstance(var.type, ListType):
                    raise ParserError('cannot append to non-list variable "%s" (type: %s)' %
                                      (varname, var.type))
                if isinstance(value, ListExpr):
                    new_values = value.items
                else:
                    new_values = [value]
                if isinstance(var.value, ListExpr):
                    value = ListExpr(var.value.items + new_values)
                else:
                    value = ListExpr([var.value] + new_values)
                value.pos = node.pos
                var.set_value(value)
            else:
                if not isinstance(var.value, NullExpr):
                    # Preserve previous value. Consider this code:
                    #   foo = one
                    #   if ( someCond ) foo = two
                    value.value_no = var.value
                var.set_value(value)


    def on_sources_or_headers(self, node):
        # TODO: handling this as AppendNode is temporary hack until the
        # source/header statement grows more syntactically complicated
        self.on_assignment(node)


    def on_target(self, node):
        name = node.name.text
        if name in self.context.targets:
            raise ParserError("target ID \"%s\" not unique" % name)

        if self.active_if_cond:
            raise ParserError("conditionally built targets not supported yet"
                              ' (condition "%s" set at %s)' % (
                                  self.active_if_cond, self.active_if_cond.pos))

        type_name = node.type.text
        try:
            target_type = TargetType.get(type_name)
            target = Target(self.context, name, target_type)
            self.context.add_target(target)
        except KeyError:
            raise ParserError("unknown target type \"%s\"" % type_name)

        # handle target-specific variables assignments etc:
        self.handle_children(node.content, target)


    def on_if(self, node):
        cond = self._build_expression(node.cond)
        if self.active_if_cond:
            # combine this condition with the outer 'if':
            cond = BoolExpr(BoolExpr.AND,
                            self.active_if_cond,
                            cond,
                            pos=node.pos)
        self.if_stack.append(cond)
        self.handle_children(node.content, self.context)
        self.if_stack.pop()


    _ast_dispatch = {
        AssignmentNode : on_assignment,
        AppendNode     : on_assignment,
        FilesListNode  : on_sources_or_headers,
        TargetNode     : on_target,
        IfNode         : on_if,
        NilNode        : lambda self,x: x, # do nothing
    }


    def _build_expression(self, ast):
        t = type(ast)
        if t is LiteralNode:
            # FIXME: type handling
            e = LiteralExpr(ast.text)
        elif t is VarReferenceNode:
            e= ReferenceExpr(ast.var, self.context)
        elif t is ListNode:
            items = [self._build_expression(e) for e in ast.values]
            e = ListExpr(items)
        elif t is ConcatNode:
            items = [self._build_expression(e) for e in ast.values]
            e = ConcatExpr(items)
        elif isinstance(ast, BoolNode):
            e = self._build_bool_expression(ast)
        else:
            assert False, "unrecognized AST node (%s)" % ast
        e.pos = ast.pos
        return e


    def _build_bool_expression(self, ast):
        t = type(ast)
        if t is NotNode:
            return BoolExpr(BoolExpr.NOT, self._build_expression(ast.left))
        else:
            if t is AndNode:
                op = BoolExpr.AND
            elif t is OrNode:
                op = BoolExpr.OR
            elif t is EqualNode:
                op = BoolExpr.EQUAL
            elif t is NotEqualNode:
                op = BoolExpr.NOT_EQUAL
            left = self._build_expression(ast.left)
            right = self._build_expression(ast.right)
            return BoolExpr(op, left, right)
