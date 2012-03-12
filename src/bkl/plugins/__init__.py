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

import sys
import logging
__logger = logging.getLogger("bkl.plugins")


def __find_all_plugins(paths):
    """
    Finds all Bakefile plugins in given directories that aren't loaded yet and
    yields them.
    """
    from os import walk
    from os.path import splitext
    x = []
    for dirname in paths:
        for root, dirs, files in walk(dirname):
            for f in files:
                basename, ext = splitext(f)
                if ext != ".py":
                    continue
                if basename == "__init__":
                    continue
                x.append(basename)
    return x


# import all plugins:
__all__ = __find_all_plugins(__path__)
from . import *
assert __all__, "No plugins found - broken Bakefile installation?"

__logger.debug("loaded plugins:")
for p in __all__:
    m = sys.modules["bkl.plugins.%s" % p]
    __logger.debug("    %s (from %s)", m.__name__, m.__file__)
