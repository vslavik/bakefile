#
#  This file is part of Bakefile (http://www.bakefile.org)
#
#  Copyright (C) 2009 Vaclav Slavik
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
Standard properties for extensions or model parts with properties.
"""

import expr, api
from vartypes import IdType, EnumType, ListType
from api import Property

#: Standard :class:`bkl.api.Module` properties
STD_MODULE_PROPS = None
#: Standard :class:`bkl.api.TargetType` properties
STD_TARGET_PROPS = None



def _init():
    """
    Initializes standard props, i.e. puts them everywhere they should be,
    e.g. into api.TargetType.properties.
    """

    global STD_MODULE_PROPS
    global STD_TARGET_PROPS

    # ----------------------------------------------------------------
    # standard module properties
    # ----------------------------------------------------------------

    toolsets_enum_type = EnumType(api.Toolset.implementations.keys())

    STD_MODULE_PROPS = [
        Property("toolsets",
                 type=ListType(toolsets_enum_type),
                 default=expr.ListExpr([]),
                 doc="List of toolsets to generate makefiles/projects for."),
        ]

    # ----------------------------------------------------------------
    # standard target properties
    # ----------------------------------------------------------------

    STD_TARGET_PROPS = [
        Property("id",
                 type=IdType(),
                 default=lambda t: expr.ConstExpr(t.name),
                 readonly=True,
                 doc="Target's unique name (ID)."),
        ]


    api.TargetType.properties = STD_TARGET_PROPS
