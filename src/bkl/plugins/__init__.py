#
#  This file is part of Bakefile (http://bakefile.org)
#
#  Copyright (C) 2012-2013 Vaclav Slavik
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


def load_from_file(filename):
    """
    Load a Bakefile plugin from given file.
    """
    import os.path
    import imp
    from bkl.error import Error
    basename = os.path.splitext(os.path.basename(filename))[0]
    if basename.startswith("bkl.plugins."):
        modname = basename
    else:
        modname = "bkl.plugins.%s" % basename.replace(".", "_")

    if modname in sys.modules:
        prev_file = sys.modules[modname].__file__
        if filename == prev_file or filename == prev_file[:-1]: #.pyc->.py
            # plugin already loaded from this file, skip it
            __logger.debug("plugin %s from %s is already loaded, nothing to do", modname, filename)
            return
        else:
            raise Error("cannot load plugin %s from %s: plugin with the same name already loaded from %s" %
                        (modname, filename, prev_file))

    try:
        global __all__
        __logger.debug("loading plugin %s from %s", modname, filename)
        globals()[basename] = imp.load_source(modname, filename)
        __all__.append(basename)
    except Error:
        raise
    except IOError as e:
        raise Error("failed to load plugin %s:\n%s" % (filename, e))
    except Exception:
        import traceback
        raise Error("failed to load plugin %s:\n%s" % (filename, traceback.format_exc()))


def __find_all_plugins():
    """
    Finds all Bakefile plugins and yields them.
    """
    import pkgutil

    if hasattr(sys, 'frozen'):
        # Special handling for PyInstaller, which as of v3.4 doesn't support walk_packages
        # (see https://github.com/pyinstaller/pyinstaller/issues/1905)
        toc = set()
        for importer in pkgutil.iter_importers(__name__):
            if hasattr(importer, 'toc'):
                toc |= importer.toc
        for name in toc:
            if name.startswith(__name__ + '.'):
                yield name[len(__name__) + 1:]
    else:
        for _, name, _ in pkgutil.walk_packages(__path__):
            yield name


# import all plugins:
__all__ = list(__find_all_plugins())
from . import *
assert __all__, "No plugins found - broken Bakefile installation?"

__logger.debug("loaded plugins:")
for p in __all__:
    m = sys.modules["bkl.plugins.%s" % p]
    __logger.debug("    %-25s (from %s)", m.__name__, m.__file__)
