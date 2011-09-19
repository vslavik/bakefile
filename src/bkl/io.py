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
Helper classes for Bakefile I/O. Manages atomic writing of output, detecting
changes, line endings conversions etc.
"""

import logging
logger = logging.getLogger("bkl.io")


EOL_WINDOWS = "win"
EOL_UNIX    = "unix"


class OutputFile(object):
    """
    File to be written by Bakefile.

    Example usage:

    ::

      f = io.OutputFile("Makefile")
      f.write(body)
      f.commit()

    Notice the need to explicitly call commit().
    """
    def __init__(self, filename, eol):
        """
        Creates output file.

        :param filename: Name of the output file. Should be either relative
                         to CWD or absolute; the latter is recommended.
        :param eol:      Line endings to use. One of EOL_WINDOWS and EOL_UNIX.
        """
        self.filename = filename
        self.eol = eol
        self.text = ""

    def write(self, text):
        """
        Writes text to the output, performing line endings conversion as
        needed. Note that the changes don't take effect until you call
        commit().
        """
        self.text += text

    def commit(self):
        if self.eol == EOL_WINDOWS:
            self.text = self.text.replace("\n", "\r\n")

        try:
            with open(self.filename, "rt") as f:
                old = f.read()
        except IOError:
            old = None
        
        if old == self.text:
            logger.info("no changes in file %s" % self.filename)
        else:
            if old is None:
                logger.info("creating file %s" % self.filename)
            else:
                logger.info("updating file %s" % self.filename)
            with open(self.filename, "wt") as f:
                f.write(self.text)
