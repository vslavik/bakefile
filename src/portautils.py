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
#  Portable utilities for misc tasks
#

import os, tempfile

def __mktemp_secure(prefix):
    """Uses tempfile.mkstemp() to atomically create named file, but works
       only with Python 2.3+."""
    handle, filename = tempfile.mkstemp(prefix=prefix)
    os.close(handle)
    return filename
    
def __mktemp_insecure(prefix):
    """Fallback version for older Python."""
    filename = tempfile.mktemp(prefix)
    # reduce (not eliminate!) the risk of race condition by immediately
    # creating the file:
    tmpf = open(filename, 'wb')
    tmpf.close()
    os.chmod(filename, 0600)
    return filename

try:
    mktemp = tempfile.mkstemp # triggers exception if not available
    mktemp = __mktemp_secure
except AttributeError:
    mktemp = __mktemp_insecure
