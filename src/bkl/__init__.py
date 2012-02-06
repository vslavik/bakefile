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

import sys, os, os.path
import imp
import logging


logger = logging.getLogger("bkl.plugins")


def load_plugin(filename):
    """
    Loads Bakefile plugin from given file.
    """
    basename = os.path.splitext(os.path.basename(filename))[0]
    modname = "bkl.plugins.%s" % basename
    logger.debug("loading plugin %s from %s", modname, filename)

    if modname in sys.modules:
        from bkl.error import Error
        raise Error("cannot load plugin %s from %s: already loaded from %s" %
                    (modname, filename, sys.modules[modname].__file__))

    imp.load_source(modname, filename)


def find_all_plugins(paths):
    """
    Finds all Bakefile plugins in given directories and yields them.
    """
    for dirname in paths:
        for root, dirs, files in os.walk(dirname):
            for f in files:
                if not f.endswith(".py"):
                    continue
                if f == "__init__.py":
                    continue
                filename = os.path.join(root, f)
                yield filename


# import all plugins:

PLUGINS_PATH = [os.path.join(p, "plugins") for p in __path__]
logger.debug("plugins search path: %s", PLUGINS_PATH)

plugin_files = list(find_all_plugins(PLUGINS_PATH))
assert plugin_files, "No plugins found - broken Bakefile installation?"

sys.modules["bkl.plugins"] = imp.new_module("bkl.plugins")
for fn in plugin_files:
    load_plugin(fn)
