# 
# Reading, parsing and checking against FORMATS.bkmanifest manifest
# files.
#
# $Id$
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
            raise erorrs.ReaderError(fmt, 'format not fully described')
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
