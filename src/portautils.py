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

#
# Secure temporary file creation:
#

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


#
# Cross-platform file locking:
# (based on portalocker Python Cookbook recipe
# by John Nielsen <nielsenjf@my-deja.com>:
# http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/65203
#

if os.name == 'nt':
    import win32con
    import win32file
    import pywintypes
    # is there any reason not to reuse the following structure?
    __overlapped = pywintypes.OVERLAPPED()

    def lock(file):
        hfile = win32file._get_osfhandle(file.fileno())
        win32file.LockFileEx(hfile, win32con.LOCKFILE_EXCLUSIVE_LOCK,
                             0, 0x7fffffff, __overlapped)

    def unlock(file):
        hfile = win32file._get_osfhandle(file.fileno())
        win32file.UnlockFileEx(hfile, 0, 0x7fffffff, __overlapped)

elif os.name == 'posix':
    import fcntl
    
    def lock(file):
        fcntl.flock(file.fileno(), fcntl.LOCK_EX)

    def unlock(file):
        fcntl.flock(file.fileno(), fcntl.LOCK_UN)

else:
    def lock(file): pass
    def unlock(file): pass
