#!/usr/bin/env python
# $Id$

import sys, os, os.path, glob, fnmatch, tempfile
from optik import OptionParser
import xmlparser, dependencies, errors
from errors import ReaderError

verbose = 0

class FileInfo:
    def __init__(self, filename):
        self.filename = filename
        self.flags = {} # key: format
        self.formats = []

files = {}

def loadTargets(filename):

    def _loadFile(filename):
        if verbose:
            print 'loading task description from %s...' % filename
        root = xmlparser.parseFile(filename)
        ret = []
        for cmd in root.children:
            if cmd.name == 'include':
                inc = os.path.join(os.path.dirname(filename), cmd.props['file'])
                if os.path.isfile(inc):
                    r2 = _loadFile(inc)
                    ret += r2.children
                else:
                    if ('ignore_missing' not in cmd.props) or \
                       (cmd.props['ignore_missing'] == '0'):
                           raise ReaderError(cmd, "file '%s' doesn't exist" % inc)
            else:
                ret.append(cmd)
        root.children = ret
        return root

    def _matchesWildcard(filename, wildcard):
        """Returns whether the file matches wildcard (glob)."""
        name = filename.split(os.sep)
        wild = wildcard.split(os.sep)
        if len(name) != len(wild):
            return 0
        for i in range(0,len(name)):
            if name[i] == wild[i]: continue
            if not fnmatch.fnmatch(name[i], wild[i]):
                return 0
        return 1

    def _findMatchingFiles(node):
        """Returns list of FileInfo objects from 'files' variable that match
           node's file matching properties ("files"=comma-sep list of wildcards,
           "formats"=comma-separated list of formats)."""
        global files
        # match filenames:
        if 'files' in node.props:
            matches1 = []
            globs = node.props['files'].split(',')
            for g in globs:
                for f in [x for x in files if _matchesWildcard(x,g)]:
                    matches1.append(files[f])
        else:
            matches1 = files.values()
        # match formats:
        if 'formats' in node.props:
            formats = node.props['formats'].split(',')
            matches2 = []
            for f in matches1:
                formats2 = [x for x in formats if x in f.formats]
                matches2.append((f,formats2))
        else:
            matches2 = []
            for f in matches1:
                matches2.append((f, f.formats))
        return matches2
   
    root = _loadFile(filename)
    
    if root.name != 'bakefile-gen':
        raise ReaderError(e, 'incorrect root node')
    
    if verbose:
        print 'scanning directories for bakefiles...'

    for cmd in [x for x in root.children if x.name == 'input']:
        globs = cmd.value.split()
        for g in globs:
            for f in glob.glob(g):
                files[f] = FileInfo(f)
    
    if verbose:
        print 'building rules...'
    
    for cmd in root.children:
        if cmd.name == 'add-formats':
            formats = cmd.value.split(',')
            for file, fl in _findMatchingFiles(cmd):
                for f in formats:
                    if f not in file.formats:
                        file.formats.append(f)
                        file.flags[f] = ''
        elif cmd.name == 'del-formats':
            formats = cmd.value.split(',')
            for file, fl in _findMatchingFiles(cmd):
                for f in formats:
                    if f in file.formats:
                        file.formats.remove(f)
                        del file.flags[f]
    
    for cmd in root.children:
        if cmd.name == 'add-flags':
            for file, formats in _findMatchingFiles(cmd):
                flags = cmd.value
                flags = flags.replace('$(INPUT_FILE)', file.filename)
                flags = flags.replace('$(INPUT_FILE_BASENAME)',
                        os.path.basename(file.filename))
                flags = flags.replace('$(INPUT_FILE_BASENAME_NOEXT)',
                        os.path.splitext(os.path.basename(file.filename))[0])
                for fmt in formats:
                    file.flags[fmt] = '%s %s' % (file.flags[fmt], flags)
        elif cmd.name == 'del-flags':
            for file, formats in _findMatchingFiles(cmd):
                for fmt in formats:
                    file.flags[fmt] = file.flags[fmt].replace(cmd.value,'')


def updateTargets():
    """Updates all targets."""
    if verbose:
        print 'determining which makefiles are out of date...'

    try:
        dependencies.load('.bakefile_gen.state')
    except IOError: pass

    needUpdate = []
    total = 0
    for f in files:
        for fmt in files[f].formats:
            total += 1
            if dependencies.needsUpdate(os.path.abspath(f), fmt):
                needUpdate.append((f,fmt))
    if verbose:
        print '    ...%i out of %i will be updated' % (len(needUpdate),total)

    total = len(needUpdate)
    i = 1
    temp = tempfile.mktemp()
    try:
        for f,fmt in needUpdate:
            print '[%i/%i] generating %s from %s' % (i, total, fmt, f)        
            i += 1
            cmd = 'bakefile -f%s %s %s --output-deps=%s' % \
                    (fmt, files[f].flags[fmt], f, temp)
            if verbose >= 2: cmd += ' -v'
            if verbose:
                print cmd
            if os.system(cmd) != 0:
                raise errors.Error('bakefile exited with error')
            dependencies.load(temp)
    finally:
        if os.path.isfile(temp):
            os.remove(temp)
        dependencies.save('.bakefile_gen.state')


def run(args):
    parser = OptionParser()
    parser.add_option('-f', '--format',
                      action="store", dest='format',
                      help='format of generated makefile')
    parser.add_option('-v', '--verbose',
                      action="store_true", dest='verbose', default=0,
                      help='display detailed information')
    parser.add_option('-V', '--very-verbose',
                      action="store_true", dest='very_verbose', default=0,
                      help='display even more detailed information')

    options, args = parser.parse_args(args)

    if len(args) != 1:
        parser.error('exactly 1 Makefiles.xml file required')
        sys.exit(1)

    global verbose
    if options.very_verbose:
        verbose = 2
    elif options.verbose:
        verbose = 1
    
    try:
        loadTargets(os.path.abspath(args[0]))
        updateTargets()
    except errors.ErrorBase, e:
        sys.stderr.write('[bakefile_gen] %s' % str(e))
        sys.exit(1)



if __name__ == '__main__':
    try:
        run(sys.argv[1:])
    except KeyboardInterrupt:
        sys.stderr.write('\nerror: bakefile_gen cancelled by user\n')
        sys.exit(1)
