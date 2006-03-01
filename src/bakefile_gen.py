#!/usr/bin/env python

#
#  This file is part of Bakefile (http://bakefile.sourceforge.net)
#
#  Copyright (C) 2003-2006 Vaclav Slavik
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

import sys, os, os.path, glob, fnmatch, threading, shutil
try:
    from optparse import OptionParser
except ImportError:
    from optik import OptionParser

import xmlparser, dependencies, errors, portautils
from errors import ReaderError

verbose = 0

class FileInfo:
    def __init__(self, filename):
        self.filename = filename
        self.flags = {} # key: format
        self.formats = []

files = {}
files_all = files

disabled_formats = []

_bakefileExecutable = None
def _getBakefileExecutable():
    """Returns command that should be used to run Bakefile. Makes sure same
       Python version as for bakefile_gen is used (if you run it e.g.
       "python2.3 bakefile_gen.py")."""
    global _bakefileExecutable
    if _bakefileExecutable == None:
        if os.path.basename(sys.executable).lower() == 'bakefile_gen.exe':
            # we're on Windows and using the wrapper binary, use bakefile.exe:
            _bakefileExecutable = '"%s"' % \
                                  os.path.join(os.path.dirname(sys.executable),
                                               'bakefile.exe')
        else:
            # find the location of bakefile.py:
            bakefile_py = os.path.normpath(os.path.join(
                            os.path.dirname(os.path.realpath(sys.argv[0])),
                            'bakefile.py'))
            _bakefileExecutable = '%s "%s"' % (sys.executable, bakefile_py)
    return _bakefileExecutable


def _matchesWildcard(filename, wildcard, absolutize=0):
    """Returns whether the file matches wildcard (glob)."""
    if absolutize:
        name = os.path.abspath(filename).split(os.sep)
        wild = os.path.abspath(wildcard).split(os.sep)
    else:
        name = filename.split(os.sep)
        wild = wildcard.split(os.sep)
    if len(name) != len(wild):
        return 0
    for i in range(0,len(name)):
        if name[i] == wild[i]: continue
        if not fnmatch.fnmatch(name[i], wild[i]):
            return 0
    return 1

def loadTargets(filename, defaultFlags=''):

    def _loadFile(filename):
        if verbose:
            print 'loading task description from %s...' % filename
        try:
            root = xmlparser.parseFile(filename)
        except xmlparser.ParsingError:
            raise errors.Error("can't load file '%s'" % filename)
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

    def _findMatchingFiles(node):
        """Returns list of FileInfo objects from 'files' variable that match
           node's file matching properties ("files"=comma-sep list of wildcards,
           "formats"=comma-separated list of formats)."""
        global files
        # match filenames:
        if 'files' in node.props:
            matches1 = []
            globs = node.props['files'].replace('/',os.sep).split(',')
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
        globs = cmd.value.replace('/', os.sep).split()
        for g in globs:
            for f in glob.glob(g):
                files[f] = FileInfo(f)
    
    if verbose:
        print 'building rules...'
    
    for cmd in root.children:
        if cmd.name == 'disable-formats':
            formats = cmd.value.split(',')
            for f in formats:
                if f not in disabled_formats:
                    disabled_formats.append(f)
        elif cmd.name == 'enable-formats':
            formats = cmd.value.split(',')
            for f in formats:
                if f in disabled_formats:
                    disabled_formats.remove(f)
    
    for cmd in root.children:
        if cmd.name == 'add-formats':
            formats = [x for x in cmd.value.split(',') 
                               if x not in disabled_formats]
            for file, fl in _findMatchingFiles(cmd):
                for f in formats:
                    if f not in file.formats:
                        file.formats.append(f)
                        file.flags[f] = defaultFlags
        elif cmd.name == 'del-formats':
            formats = [x for x in cmd.value.split(',') 
                               if x not in disabled_formats]
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
                flags = flags.replace('$(INPUT_FILE_DIR)',
                        os.path.dirname(file.filename))
                for fmt in formats:
                    file.flags[fmt] = '%s %s' % (file.flags[fmt], flags)
        elif cmd.name == 'del-flags':
            for file, formats in _findMatchingFiles(cmd):
                for fmt in formats:
                    file.flags[fmt] = file.flags[fmt].replace(cmd.value,'')



def filterFiles(bakefiles, formats):
    global files, files_all
    files_all = files
    if bakefiles == None:
        files1 = files
    else:
        files1 = {}
        for f in files:
            for wildcard in bakefiles:
                if _matchesWildcard(f, wildcard, absolutize=1):
                    files1[f] = files[f]
                    break
    files = files1
    
    if formats != None:
        for f in files.values():
            f.formats = [x for x in f.formats if x in formats]



def updateTargets(jobs, pretend=0, keepGoing=0, alwaysMakeAll=0):
    """Updates all targets. Run jobs instances of bakefile simultaneously"""
    if verbose:
        if alwaysMakeAll:
            print 'pretending all makefiles are out of date...'
        else:
            print 'determining which makefiles are out of date...'

    needUpdate = []
    total = 0
    
    # load the state file with dependencies even when using --always-make
    # so that running bakefile_gen --always-make doesn't invalidate all
    # dependencies if it doesn't finish:
    try:
        dependencies.load('.bakefile_gen.state')
    except IOError: pass

    if alwaysMakeAll:
        # uncoditionally add all bakefiles to the list of bakefiles which
        # need to be regenerated:
        for f in files:
            for fmt in files[f].formats:
                total += 1
                needUpdate.append((f,fmt))
    else:
        # load bakefile_gen state file and choose only bakefiles out of date:
        for f in files:
            for fmt in files[f].formats:
                total += 1
                if dependencies.needsUpdate(os.path.abspath(f),
                                            fmt,
                                            cmdline=files[f].flags[fmt]):
                    needUpdate.append((f,fmt))
    
    if verbose:
        print '    ...%i out of %i will be updated' % (len(needUpdate),total)
    
    def __countLines(fn):
        try:
            f = open(fn, 'rt')
            cnt = len(f.readlines())
            f.close()
            return cnt
        except IOError:
            return 0

    class UpdateState:
        def __init__(self):
            self.modifiedFiles = 0
            self.needUpdate = []
            self.totalCount = 0
            self.done = 0

    def _doUpdate(state, job, pretend=0):
        if job == None: threadId = ''
        else: threadId = '(%i)' % job
        tempDeps = portautils.mktemp('bakefile')
        tempChanges = portautils.mktemp('bakefile')
        tempXmlCacheDir = portautils.mktempdir('bakefile')
        tempXmlCacheFile = os.path.join(tempXmlCacheDir, 'xmlcache')

        try:
            while 1:
                try:
                    state.lock.acquire()
                    if len(state.needUpdate) == 0: break
                    f, fmt = state.needUpdate.pop()
                    state.done += 1
                    i = state.done
                finally:
                    state.lock.release()
                print '%s[%i/%i] generating %s from %s' % (
                            threadId, i, state.totalCount, fmt, f)
                cmd = '%s -f%s %s %s --output-deps=%s --output-changes=%s --xml-cache=%s' % \
                        (_getBakefileExecutable(),
                         fmt, files[f].flags[fmt], f,
                         tempDeps, tempChanges, tempXmlCacheFile)
                if verbose >= 2: cmd += ' -v'
                if verbose:
                    print cmd
                if pretend: continue

                if os.system(cmd) != 0:
                    if keepGoing:
                        sys.stderr.write(
                          '[bakefile_gen] bakefile exited with error, ignoring')
                        continue
                    else:
                        raise errors.Error('bakefile exited with error')
                modLinesCnt = __countLines(tempChanges)
                try:
                    state.lock.acquire()
                    dependencies.load(tempDeps)
                    dependencies.addCmdLine(os.path.abspath(f), fmt,
                                            files[f].flags[fmt])
                    state.modifiedFiles += modLinesCnt
                finally:
                    state.lock.release()
        finally:
            os.remove(tempDeps)
            os.remove(tempChanges)
            shutil.rmtree(tempXmlCacheDir)
            try:
                state.lock.acquire()
                state.activeThreads -= 1
                if state.activeThreads == 0:
                    state.lockAllDone.release()
            finally:
                state.lock.release()

    class UpdateThread(threading.Thread):
        def __init__(self, state, job):
            threading.Thread.__init__(self)
            self.state = state
            self.job = job
        def run(self):
            _doUpdate(self.state, self.job)

    state = UpdateState()
    state.needUpdate = needUpdate
    state.totalCount = len(needUpdate)
    state.lock = threading.Lock()
    state.lockAllDone = threading.Lock()
    state.activeThreads = jobs

    if pretend: jobs = 1

    try:
        state.lockAllDone.acquire()
        if jobs == 1:
            _doUpdate(state, None, pretend=pretend)
        else:
            for i in range(0, jobs-1):
                t = UpdateThread(state, i)
                t.setDaemon(1)
                t.start()
            
            _doUpdate(state, jobs-1)                
            # wait until everybody finishes (the thread that sets
            # activeThreads to 0 will release the lock):
            state.lockAllDone.acquire()
            state.lockAllDone.release()
        if pretend:
            return
    finally:
        try:
            state.lock.acquire()
            dependencies.save('.bakefile_gen.state')
        finally:
            state.lock.release()

    print '%i files modified' % state.modifiedFiles


def cleanTargets(pretend=0):
    try:
        dependencies.load('.bakefile_gen.state')
    except IOError: pass

    def _isGeneratedBySomethingElse(output):
        """Returns true if the file is output of some file in files_all
           that is not part of files."""
        for f in files_all:
            if f in files: continue
            formats = files_all[f].formats
            absf = os.path.abspath(f)
            for fmt in formats:
               for o,m in dependencies.deps_db[(absf,fmt)].outputs:
                   if output == o: return 1
        return 0

    for f in files:
        for fmt in files[f].formats:
            key = (os.path.abspath(f), fmt)
            if key not in dependencies.deps_db:
                sys.stderr.write("ERROR: don't know how to clean %s generated from %s\n" % (fmt, f))
            else:
                for o, method in dependencies.deps_db[key].outputs:
                    if not os.path.isfile(o): continue
                    if method not in ['replace','mergeBlocks']: continue
                    if _isGeneratedBySomethingElse(o): continue
                    if verbose: print 'deleting %s' % o
                    if pretend:
                        print 'rm %s' % o
                    else:
                        os.remove(o)


def run(args):
    parser = OptionParser()
    parser.add_option('-d', '--desc',
                      action="store", dest='descfile',
                      default='Bakefiles.bkgen',
                      help='load description from DESCFILE instead of from Bakefiles.bkgen')
    parser.add_option('-f', '--formats',
                      action="append", dest='formats',
                      help='only generate makefiles in these formats (comma-separated list)')
    parser.add_option('-b', '--bakefiles',
                      action="append", dest='bakefiles',
                      help='only generate makefiles from bakefiles that are matched by these wildcards (comma-separated list)')
    parser.add_option('-D',
                      action="append", dest='defines', metavar='VAR=VALUE',
                      help="add variable or option definition in addition to -D options defined in Bakefiles.bkgen's <add-flags>")
    parser.add_option('-c', '--clean',
                      action="store_true", dest='clean',
                      default=0,
                      help='clean generated files, don\'t create them')
    parser.add_option('-j', '--jobs',
                      action="store", dest='jobs',
                      default='1',
                      help='number of jobs to run simultaneously')
    parser.add_option('-p', '--pretend',
                      action="store_true", dest='pretend',
                      default=0,
                      help="don't do anything, only display actions that would be performed")
    parser.add_option('-k', '--keep-going',
                      action="store_true", dest='keepGoing',
                      default=0,
                      help="keep going when some targets can't be made")
    parser.add_option('-B', '--always-make',
                      action="store_true", dest='alwaysMakeAll',
                      default=0,
                      help="unconditionally generate all makefiles even if they are up to date")
    parser.add_option('-v', '--verbose',
                      action="store_true", dest='verbose', default=0,
                      help='display detailed information')
    parser.add_option('-V', '--very-verbose',
                      action="store_true", dest='very_verbose', default=0,
                      help='display even more detailed information')

    options, args = parser.parse_args(args)

    global verbose
    if options.very_verbose:
        verbose = 2
    elif options.verbose:
        verbose = 1

    if options.formats != None:
        options.formats = ','.join(options.formats)
        options.formats = options.formats.split(',')
    if options.bakefiles != None:
        options.bakefiles = ','.join(options.bakefiles)
        options.bakefiles = options.bakefiles.replace('/',os.sep).split(',')
    options.jobs = int(options.jobs)

    moreDefines=''
    if options.defines != None:
        moreDefines = ' '.join(['-D%s' % x for  x in options.defines])
 
    try:
        loadTargets(os.path.abspath(options.descfile), moreDefines)
        filterFiles(options.bakefiles, options.formats)
        if options.clean:
            cleanTargets(pretend=options.pretend)
        else:
            updateTargets(jobs=options.jobs,
                          pretend=options.pretend,
                          keepGoing=options.keepGoing,
                          alwaysMakeAll=options.alwaysMakeAll)
    except errors.ErrorBase, e:
        sys.stderr.write('[bakefile_gen] %s' % str(e))
        sys.exit(1)



if __name__ == '__main__':
    if sys.version_info[0:3] < (2,2,2):
        sys.stderr.write('error: Bakefile requires at least Python 2.2.2\n')
        sys.exit(1)
        
    try:
        run(sys.argv[1:])
    except KeyboardInterrupt:
        sys.stderr.write('\nerror: bakefile_gen cancelled by user\n')
        sys.exit(1)
