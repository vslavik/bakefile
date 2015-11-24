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
Helper classes for Bakefile I/O. Manages atomic writing of output, detecting
changes, line endings conversions etc.
"""

import os
import os.path

import logging
logger = logging.getLogger("bkl.io")


# Set to true to prevent any output from being written
dry_run = False

# Set to true to show diff with the existing file instead of updating it
diff_only = False

# Set to true to force writing of output files, even if they exist and would be
# unchanged. In other words, always touch output files. This is useful for
# makefiles that support automatic regeneration.
force_output = False

# Number of created files
num_created = 0
# Number of modified files
num_modified = 0

EOL_WINDOWS = "win"
EOL_UNIX    = "unix"

_all_written_files = {}

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
    def __init__(self, filename, eol, charset="utf-8",
                 creator=None, create_for=None):
        """
        Creates output file.

        :param filename: Name of the output file. Should be either relative
                         to CWD or absolute; the latter is recommended.
        :param eol:      Line endings to use. One of EOL_WINDOWS and EOL_UNIX.
        :param charset:  Charset to use if Unicode string is passed to write().
        :param creator:  Who is creating the file; typically toolset object.
        :param create_for: Object the file is created for, e.g. a module or a target.
        """
        if filename in _all_written_files:
            creator1, create_for1 = _all_written_files[filename]
            from bkl.error import Error
            raise Error("conflict in file %(filename)s, generated both by %(creator1)s for %(create_for1)s and %(creator)s for %(create_for)s" % locals())
        _all_written_files[filename] = (creator, create_for)

        self.filename = filename
        self.eol = eol
        self.charset = charset
        self.text = ""

    def write(self, text):
        """
        Writes text to the output, performing line endings conversion as
        needed. Note that the changes don't take effect until you call
        commit().
        """
        if isinstance(text, unicode):
            text = text.encode(self.charset)
        self.text += text

    def replace(self, placeholder, value):
        """
        Replaces the value of the given placeholder with its real value. This
        is useful for parts of the output which are not known at the time they
        are written because they depend on other parts coming after them.

        Notice that only the first occurrency of the placeholder is replaced.
        """
        self.text = self.text.replace(placeholder, value, 1)

    def commit(self):
        if self.eol == EOL_WINDOWS:
            self.text = self.text.replace("\n", "\r\n")
        try:
            rel_fn = os.path.relpath(self.filename)
        except ValueError:
            # This can happen under Windows if the filename is on a different
            # drive from the current directory, in this case we have no other
            # choice but to use the absolute path to it.
            rel_fn = self.filename

        if not force_output:
            try:
                with open(self.filename, "rb") as f:
                    old = f.read()
            except IOError:
                old = None
            if old == self.text:
                status = "."
                logger.info("%s\t%s", status, rel_fn)
                return
            if diff_only:
                import sys
                from difflib import unified_diff
                for line in unified_diff(old.splitlines(True) if old is not None else [],
                                         self.text.splitlines(True),
                                         os.path.normpath(os.path.join("old", self.filename)),
                                         os.path.normpath(os.path.join("new", self.filename))):
                    sys.stdout.write(line)
                return
        else:
            old = None

        global num_created, num_modified
        if old is None:
            status = "A"
            num_created += 1
        else:
            status = "U"
            num_modified += 1

        logger.info("%s\t%s", status, rel_fn)

        if dry_run:
            return # nothing to do, just pretending to write output

        dirname = os.path.dirname(self.filename)
        if dirname and not os.path.isdir(dirname):
            os.makedirs(dirname)
        with open(self.filename, "wb") as f:
            f.write(self.text)
