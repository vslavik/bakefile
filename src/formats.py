#
#  This file is part of Bakefile (http://www.bakefile.org)
#
#  Copyright (C) 2003,2004 Vaclav Slavik
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
