#!/usr/bin/env python

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

import sys, os, os.path, glob, fnmatch, shutil, re
from optparse import OptionParser

if sys.version_info < (2,5):
    import config
    sys.path.append(os.path.join(config.progdir, 'py25modules'))


import xmlparser, dependencies, errors, portautils
from errors import ReaderError

import subprocess

verbose = 0

def _get_num_of_cpus():
    """Detects number of available processors/cores"""
    if os.name == 'nt':
        try:
            return max(1, int(os.environ['NUMBER_OF_PROCESSORS']))
        except KeyError: pass
        except ValueError: pass
    elif os.name == 'posix':
        try:
            return max(1, int(os.sysconf('SC_NPROCESSORS_ONLN')))
        except ValueError:
            try:
                return max(1, int(os.sysconf('SC_NPROCESSORS_CONF')))
            except ValueError:
                pass
        
        if sys.platform == 'darwin':
            # OS X < 10.5 doesn't have useful values in os.sysconf()
            try:
                if os.path.exists("/usr/sbin/sysctl"):
                    return max(1, int(os.popen2("/usr/sbin/sysctl -n hw.ncpu")[1].read().strip()))
            except ValueError:
                pass
    return 1


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
    """Returns command(s) that should be used to run Bakefile as a list
       suitable for subprocess.call. Makes sure same Python version as for
       bakefile_gen is used (if you run it e.g.  "python2.3
       bakefile_gen.py")."""
    global _bakefileExecutable
    if _bakefileExecutable == None:
        if os.path.basename(sys.executable).lower() == 'bakefile_gen.exe':
            # we're on Windows and using the wrapper binary, use bakefile.exe:
            _bakefileExecutable = [os.path.join(os.path.dirname(sys.executable),
                                                'bakefile.exe')]
        else:
            # find the location of bakefile.py:
            bakefile_py = os.path.normpath(os.path.join(
                            os.path.dirname(os.path.realpath(sys.argv[0])),
                            'bakefile.py'))
            _bakefileExecutable = [sys.executable, bakefile_py]
    # make a copy of the list so that's not modified by the caller:
    return [x for x in _bakefileExecutable]


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


def _split_format(format):
    """Splits format specification into (base) format and variant; e.g. "watcom(os2)"
       is separated into "watcom" (base format) and "os2" (variant)."""
    pos = format.find("(")
    if pos == -1:
        return (format, None)
    if format[-1] != ")":
        raise errors.Error("invalid format specification: '%s'" % format)
    return (format[:pos], format[pos+1:-1])

def _get_base_format(format):
    """Returns format's base format value (i.e. without variant)."""
    return _split_format(format)[0]


def loadTargets(filename, defaultFlags=[]):

    def _loadFile(filename):
        if verbose:
            print 'loading task description from %s...' % filename
        try:
            root = xmlparser.parseFile(filename, xmlparser.NS_BAKEFILE_GEN)
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

    def _parseFlags(cmdline):
        """Splits command line into individual flag arguments. Handles quoting
           with " properly."""
        # findall returns list of tuples, 1st or 2nd item is empty, depending
        # on which subexpression was matched:
        return [a or b for a,b in re.findall(r'"(.*?)"|(\S+)', cmdline)]
   
    root = _loadFile(filename)
    
    if root.name != 'bakefile-gen':
        raise ReaderError(root, 'incorrect root node (not a bakefile_gen file?)')
    
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
                        file.flags[f] = [x for x in defaultFlags] # make copy
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
            flagsList = _parseFlags(cmd.value)
            for file, formats in _findMatchingFiles(cmd):
                for f in flagsList:
                    flags = f
                    flags = flags.replace('$(INPUT_FILE)', file.filename)
                    flags = flags.replace('$(INPUT_FILE_BASENAME)',
                            os.path.basename(file.filename))
                    flags = flags.replace('$(INPUT_FILE_BASENAME_NOEXT)',
                            os.path.splitext(os.path.basename(file.filename))[0])
                    inputdir = os.path.dirname(file.filename)
                    if inputdir == '': inputdir = '.'
                    flags = flags.replace('$(INPUT_FILE_DIR)', inputdir)

                    for fmt in formats:
                        file.flags[fmt].append(flags)

        elif cmd.name == 'del-flags':
            flagsList = _parseFlags(cmd.value)
            for file, formats in _findMatchingFiles(cmd):
                for fmt in formats:
                    for f in flagsList:
                        try:
                            file.flags[fmt].remove(f)
                        except ValueError:
                            sys.stderr.write(
                                "Warning: trying to remove flags '%s' that weren't added at %s (current flags on file %s, format %s: '%s')\n" %
                                (f, cmd.location(), file.filename, fmt, ' '.join(file.flags[fmt])))



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
            f.formats = [x for x in f.formats if _get_base_format(x) in formats]


def _countLines(fn):
    try:
        f = open(fn, 'rt')
        cnt = len(f.readlines())
        f.close()
        return cnt
    except IOError:
        return 0


def updateTargets(jobs, pretend=False, keepGoing=False, alwaysMakeAll=False,
                  dryRun=False, quiet=False):
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
   
    totalNeedUpdate = len(needUpdate)

    if verbose:
        print '    ...%i out of %i will be updated' % (totalNeedUpdate, total)

    class JobDesc:
        def __init__(self, data, jobNum, xmlcache, pretend=False):
            self.filename, self.format = data
            self.jobNum = jobNum
            self.xmlcache = xmlcache
            self.pretend = pretend
            self.tempDeps = portautils.mktemp('bakefile')
            self.tempChanges = portautils.mktemp('bakefile')
            self.process = None
        
        def run(self):
            """Starts the subprocess."""
            if not quiet:
                print '[%i/%i] generating %s from %s' % (
                        self.jobNum, totalNeedUpdate, self.format, self.filename)
                sys.stdout.flush()
            cmd = _getBakefileExecutable()
            cmd.append('-f%s' % _get_base_format(self.format))
            cmd += files[self.filename].flags[self.format]
            cmd.append('--output-deps=%s' % self.tempDeps)
            cmd.append('--output-changes=%s' % self.tempChanges)
            cmd.append('--xml-cache=%s' % self.xmlcache)
            if quiet:
                cmd.append('--quiet')
            elif verbose >= 2:
                cmd.append('-v')
            if dryRun:
                cmd.append('--dry-run')
            cmd.append(self.filename)
            if verbose:
                print ' '.join(cmd)
            if not pretend:
                self.process = subprocess.Popen(cmd)

        def poll(self):
                if self.pretend or self.process == None:
                    return True
                return self.process.poll() != None
        
        def wait(self):
                if self.pretend or self.process == None:
                    return True
                return self.process.wait() != None
        
        def finish(self):
            try:
                try:
                    # NB: "finally" section below is still called after these
                    #     return statements
                    if self.pretend:
                        return 0
                    if self.process == None:
                        return 0

                    if self.process.returncode == 0:
                        dependencies.load(self.tempDeps)
                        dependencies.addCmdLine(os.path.abspath(self.filename), self.format,
                                                files[self.filename].flags[self.format])
                        return _countLines(self.tempChanges)
                    else: # failed, returncode != 0
                        if keepGoing:
                            sys.stderr.write(
                              '[bakefile_gen] bakefile exited with error, ignoring\n')
                            return 0 # no modified files
                        else:
                            raise errors.Error('bakefile exited with error')
                except IOError, e:
                    raise errors.Error('failed to run bakefile: %s' % e)
            finally:
                os.remove(self.tempDeps)
                os.remove(self.tempChanges)
            
  

    modifiedFiles = 0
    jobNum = 0 
    childProcessesCnt = 0
    childProcesses = [None for i in range(0,jobs)]
   
    # NB: Pre-parsed XML cache doesn't use file locking, so we have to ensure
    #     only one bakefile process will be using it at a time, by having #jobs
    #     caches. Hopefully no big deal, the cache is only really useful on
    #     large projects with shared fies and it fills pretty quickly in that
    #     case (FIXME?)
    tempXmlCacheDir = portautils.mktempdir('bakefile')
    tempXmlCacheFiles = [os.path.join(tempXmlCacheDir, 'xmlcache%i' % i) for i in range(0,jobs)]

    try:
        try:
            while len(needUpdate) > 0 or childProcessesCnt > 0:
                # start new processes:
                for p in range(0,jobs):
                    if len(needUpdate) > 0 and childProcesses[p] == None:
                        jobNum += 1
                        childProcessesCnt += 1
                        childProcesses[p] = JobDesc(needUpdate.pop(),
                                                    jobNum,
                                                    tempXmlCacheFiles[p],
                                                    pretend)
                        childProcesses[p].run()

                # check for finished processes:
                for p in range(0,jobs):
                    pr = childProcesses[p]
                    if pr != None and pr.poll():
                        childProcessesCnt -= 1
                        childProcesses[p] = None
                        modifiedFiles += pr.finish()

        # NB: using "finally" instead of "except" so that we can easily handle
        #     both Exception and KeyboardInterrupt (which is not Exception)
        #     and also to preserve exception stack trace
        finally:
            left = [p for p in childProcesses if p != None]
            if len(left) > 0:
                print '[bakefile_gen] waiting for remaining jobs to finish after error...'
                for p in left:
                    try:
                        p.wait()
                        modifiedFiles += p.finish()
                    except Exception, e:
                        pass # ignore further errors


    finally:
        shutil.rmtree(tempXmlCacheDir, ignore_errors=True)
        dependencies.save('.bakefile_gen.state')

    if not quiet:
        if dryRun:
            print '%i files would be modified' % modifiedFiles
        else:
            print '%i files modified' % modifiedFiles


def cleanTargets(pretend=False, dryRun=False):
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
                try:
                    for o,m in dependencies.deps_db[(absf,fmt)].outputs:
                        if output == o: return 1
                except KeyError:
                    pass # (absf,fmt) not in dependencies, that's OK
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
                    elif not dryRun:
                        os.remove(o)

def listOutputFiles(jobs, alwaysMakeAll=0):
    # make sure all data are current:
    updateTargets(jobs=jobs, alwaysMakeAll=alwaysMakeAll,
                  dryRun=True, quiet=True)

    # then extract and print the output files from .bakefile_gen.state:
    for f in files:
        absf = os.path.abspath(f)
        for fmt in files[f].formats:
            for outf, m in dependencies.deps_db[(absf,fmt)].outputs:
                print outf


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
    parser.add_option('', '--list-files',
                      action="store_true", dest='list_files',
                      default=0,
                      help="print the list of output files that would be generated (given -f and -b arguments) instead of creating them")
    jobsDefault = _get_num_of_cpus()
    parser.add_option('-j', '--jobs',
                      action="store", dest='jobs',
                      default=jobsDefault,
                      help='number of jobs to run simultaneously [default: %i]' % jobsDefault)
    parser.add_option('-p', '--pretend',
                      action="store_true", dest='pretend',
                      default=0,
                      help="don't do anything, only display actions that would be performed")
    parser.add_option('', '--dry-run',
                      action="store_true", dest='dryRun', default=0,
                      help="don't write any files, just pretend doing it")
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
    
    if options.clean and options.list_files:
      parser.error('--clean and --list-files are mutually exclusive')

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

    moreDefines=[]
    if options.defines != None:
        moreDefines = ['-D%s' % x for x in options.defines]
 
    try:
        loadTargets(os.path.abspath(options.descfile), moreDefines)
        filterFiles(options.bakefiles, options.formats)
        if options.clean:
            cleanTargets(pretend=options.pretend, dryRun=options.dryRun)
        elif options.list_files:
            listOutputFiles(jobs=options.jobs,
                            alwaysMakeAll=options.alwaysMakeAll)
        else:
            updateTargets(jobs=options.jobs,
                          pretend=options.pretend,
                          keepGoing=options.keepGoing,
                          alwaysMakeAll=options.alwaysMakeAll,
                          dryRun=options.dryRun)
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
