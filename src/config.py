#
#  This file is part of Bakefile (http://bakefile.sourceforge.net)
#
#  Copyright (C) 2003,2004 Vaclav Slavik
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License version 2 as
#  published by the Free Software Foundation.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
#  $Id$
#
#  Configuration holder
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
