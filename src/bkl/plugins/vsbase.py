#
#  This file is part of Bakefile (http://www.bakefile.org)
#
#  Copyright (C) 2012 Vaclav Slavik
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
Base classes for all Visual Studio toolsets.
"""

class VSProjectBase(object):
    """
    Base class for all Visual Studio projects.

    To be used by code that interfaces VS toolsets.
    """

    #: Version of the project.
    #: Uses the same format as toolsets name, so the returned value is a
    #: number, e.g. 2010.
    version = None

    #: Name of the project. Typically basename of the project file.
    name = None

    #: GUID of the project.
    guid = None

    #: Filename of the project, as :class:`bkl.expr.Expr`."""
    projectfile = None

    #: List of dependencies of this project, as names."""
    dependencies = []
