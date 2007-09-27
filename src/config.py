#
#  This file is part of Bakefile (http://www.bakefile.org)
#
#  Copyright (C) 2003-2007 Vaclav Slavik
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
#  $Id$
#
#  Configuration holder
#

import os, os.path, sys

# Be verbose:
verbose = 0
quiet = 0

# Directories where makefiles are looked for:
#   1. BAKEFILE_PATHS environment variable
#   2. if the executable is in $(foo)/lib/bakefile, then in
#      $(foo)/share/bakefile/{rules,output} if it exists, otherwise in
#      ../{rules,output} relative to executable location
#
searchPath = os.getenv('BAKEFILE_PATHS', '').split(os.pathsep)
if searchPath == ['']: searchPath = []

progdir = os.path.dirname(os.path.realpath(sys.argv[0]))
datadir = os.path.join(progdir, '..', '..', 'share', 'bakefile')
if not os.path.isfile(os.path.join(datadir, 'rules', 'FORMATS.bkmanifest')):
    datadir = os.path.join(progdir, '..')
searchPath.append(os.path.normpath(os.path.join(datadir, 'rules')))
searchPath.append(os.path.normpath(os.path.join(datadir, 'rules', 'modules')))
searchPath.append(os.path.normpath(os.path.join(datadir, 'output')))
searchPath.append(os.path.normpath(datadir))


# The way target makefiles quote variables:
variableSyntax = '$(%s)' # FIXME

# Output format:
format = None

# List of parsed output directives ((file,writer) tuples):
to_output = []

# Track dependencies (generated and used files)?:
track_deps = 0

# File to store dependencies into:
deps_file = None

# File to store list of modified output files:
changes_file = None

# If set to True, no output is written, bakefile just pretends to do it
dry_run = False

# If set to True, output files are always touched (written), even if their
# content didn't change
always_touch_output = False

# Wrap output lines at given width. If "None", no wrapping is done
wrap_lines_at = 75
