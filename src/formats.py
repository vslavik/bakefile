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
#  Reading, parsing and checking against FORMATS.bkmanifest manifest
#  files.
#

import xmlparser, errors
import config
import os.path

formats = {}

class FormatInfo:
    def __init__(self):
        self.name = None
        self.desc = None
        self.defaultFile = None

def loadManifestFile(filename):
    """Loads manifest from file 'filename'."""
    manifest = xmlparser.parseFile(filename)
    if manifest.name != 'bakefile-manifest':
        raise errors.ReaderError(manifest, 'invalid manifest file')
    for fmt in manifest.children:
        if fmt.name != 'format':
            raise errors.ReaderError(fmt, 'invalid manifest file')
        info = FormatInfo()
        info.name = fmt.props['id']        
        for node in fmt.children:
            if node.name == 'description':
                info.desc = node.value
            elif node.name == 'default-filename':
                info.defaultFile = node.value
            else:
                raise errors.ReaderError(node, 'invalid format description')
        if info.name == None or info.desc == None or info.defaultFile == None:
            raise errors.ReaderError(fmt, 'format not fully described')
        formats[info.name] = info

def loadFormats():
    """Find all format specification in search paths."""
    for path in config.searchPath:
        manifest = os.path.join(path, 'FORMATS.bkmanifest')
        if os.path.isfile(manifest):
            loadManifestFile(manifest)

def isValidFormat(f):
    return f in formats

def showFormats():
    if len(formats) == 0:
        loadFormats()

    help = "available formats are:\n"
    maxlen = 0
    for f in formats:
        if len(f) > maxlen: maxlen = len(f)
    outfmt = '    %%-%is   %%s\n' % maxlen
    keys = formats.keys()
    keys.sort()
    for f in keys:
        help += outfmt % (f, formats[f].desc)
    help += '\n'
    return help
