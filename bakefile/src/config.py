#
# Configuration holder
#
# $Id$
#

import os, os.path, sys

# Be verbose:
verbose = 0

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
if ((os.path.normpath(
        os.path.join(progdir, '..', '..', 'lib', 'bakefile')) != progdir) or
        not os.path.isdir(datadir)):
    datadir = os.path.join(progdir, '..')
searchPath.append(os.path.normpath(os.path.join(datadir, 'rules')))
searchPath.append(os.path.normpath(os.path.join(datadir, 'output')))


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
