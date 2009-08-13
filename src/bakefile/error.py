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

class Error(Exception):
    """
    Base class for all Bakefile errors.

    .. attribute:: pos

        Position object with location of the error.

    .. attribute:: msg

        Error message.
    """
    def __init__(self, pos, msg):
        """
        Constructor

        :param pos: position of the error, may be None
        :param msg: error message to show to the user
        """
        if not pos:
            pos = Position()
        self.pos = pos
        self.msg = msg


    def __unicode__(self):
        return str(self)

    def __str__(self):
        if self.pos:
            return "%s: %s" % (self.pos, self.msg)
        else:
            return self.msg



class ParserError(Error):
    """
    Exception class for errors encountered by the Bakefile parser.
    """
    pass
