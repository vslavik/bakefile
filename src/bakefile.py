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

import sys, os.path
from optparse import OptionParser

import errors
import formats
import xmlparser

def addIncludePaths(includes):
    import config
    normalized = [os.path.normpath(p) for p in includes]
    config.searchPath = normalized + config.searchPath

class BakefileOptionParser(OptionParser):
    def __init__(self):
        from version import BAKEFILE_VERSION
        OptionParser.__init__(self,
                              version='Bakefile %s' % BAKEFILE_VERSION,
                              usage='usage: %prog [options] inputfile.bkl')
    def print_help(self, file=None):
        # prepare list of available formats; we have to do it here, because
        # showFormats() may print warnings or errors to stderr and we don't
        # want that to happen in the middle of printing help
        if self.values.includes != None:
            addIncludePaths(self.values.includes)
        formatsList = formats.showFormats()

        if file is None:
            file = sys.stdout
        OptionParser.print_help(self, file)
   
        # show all available formats:
        file.write('\n%s' % formatsList)


def run(args):
    import config

    if sys.version_info < (2,5):
        sys.path.append(os.path.join(config.progdir, 'py25modules'))

    parser = BakefileOptionParser()
    parser.add_option('-f', '--format',
                      action="store", dest='format',
                      help='format of generated makefile')
    parser.add_option('-o', '--output',
                      action="store", dest='outfile',
                      help='output file')
    parser.add_option('-D',
                      action="append", dest='defines', metavar='VAR=VALUE',
                      help='override variable or option definition')
    parser.add_option('-I',
                      action="append", dest='includes', metavar='PATH',
                      help='search for bakefile rules in PATH')
    parser.add_option('-v', '--verbose',
                      action="store_true", dest='verbose', default=0,
                      help='display detailed information')
    parser.add_option('-q', '--quiet',
                      action="store_true", dest='quiet', default=0,
                      help='supress all output except of errors')
    parser.add_option('', '--dry-run',
                      action="store_true", dest='dry_run', default=0,
                      help="don't write any files, just pretend doing it")
    parser.add_option('', '--touch',
                      action="store_true", dest='always_touch_output', default=0,
                      help="always touch output files, even if their content doesn't change")
    parser.add_option('', '--eol',
                      default="format", action="store", dest='eol',
                      metavar='STYLE', type='choice',
                      choices=['format','dos','unix','mac','native'],
                      help="line endings type to use in output files (format, dos, unix, mac, native) [default: format]")
    parser.add_option('', '--wrap-output',
                      default="75", action="store", dest='wrap_lines_at',
                      metavar='LENGTH',
                      help="don't generate lines longer than LENGTH; set to \"no\" to disable wrapping [default: 75]")
    parser.add_option('', '--output-deps',
                      action="store", dest='deps_file', metavar='DEPSFILE',
                      help="output dependencies information for bakefile_gen")
    parser.add_option('', '--output-changes',
                      action="store", dest='changes_file', metavar='MODSFILE',
                      help="output list of modified files to a file")
    parser.add_option('', '--xml-cache',
                      action="store", dest='xml_cache', metavar='CACHEFILE',
                      help="cache file where bakefile_gen stores pre-parsed XML files")
    parser.add_option('', '--debug',
                      action="store_true", dest='debug', default=0,
                      help="show debugging information (you don't want this)")
    parser.add_option('', '--dump',
                      action="store_true", dest='dump', default=0,
                      help='dump parsed makefile content instead of '+
                           'generating makefile')

    options, args = parser.parse_args(args)

    if len(args) != 1:
        parser.error('incorrect number of arguments, exactly 1 .bkl required')

    config.dry_run = options.dry_run
    config.always_touch_output = options.always_touch_output
    config.debug = options.debug
    config.quiet = options.quiet
    if config.quiet:
        config.verbose = 0
    else:
        config.verbose = options.verbose

    if options.includes != None:
        addIncludePaths(options.includes)

    if options.xml_cache != None:
        try:
            # don't use shelve.open(), limit ourselves to dbhash version by
            # using the Shelf class explicitly; that's because we store large
            # chunks of data in the shelve and some dbm implementations can't
            # handle it -- see http://www.bakefile.org/ticket/214
            import pickle, shelve, dbhash
            xmlparser.cache = shelve.Shelf(dbhash.open(options.xml_cache, 'c'),
                                           protocol=pickle.HIGHEST_PROTOCOL)
        except ImportError:
            sys.stderr.write("Warning: disabling XML cache because it's not supported by this version of Python\n")
        except AttributeError: # python < 2.3 didn't have HIGHEST_PROTOCOL
            sys.stderr.write("Warning: disabling XML cache because it's not supported by Python 2.2\n")
        except KeyError: # python < 2.3 didn't have protocol argument
            sys.stderr.write("Warning: disabling XML cache because it's not supported by Python 2.2\n")
        except Exception, e:
            sys.stderr.write("Warning: disabling XML cache because an error occured while loading %s:\n         %s\n" % (options.xml_cache, e))

    formats.loadFormats()
    if options.format == None:
        parser.error('you must specify output format (use -f option)')
    config.format = options.format
    if not formats.isValidFormat(config.format):
        parser.error("unknown format '%s'\n\n" % config.format +
                     formats.showFormats())

    if options.deps_file != None:
        config.track_deps = 1
        config.deps_file = options.deps_file

    if options.changes_file != None:
        config.changes_file = options.changes_file
    
    if options.outfile != None:
        config.output_file = options.outfile
    else:
        fmt = formats.formats[config.format]
        if fmt.defaultFile == None or fmt.defaultFile == '':
            parser.error('you must specify output file (use -o option)')
        else:
            config.output_file = \
                os.path.join(os.path.dirname(args[0]), fmt.defaultFile)

    config.eol = options.eol

    if options.wrap_lines_at == "no":
        config.wrap_lines_at = None
    else:
        try:
            config.wrap_lines_at = int(options.wrap_lines_at)
        except ValueError:
            parser.error('invalid --wrap-output value: must be an integer or "no"')

    
    config.defines = {}
    if options.defines != None:
        for define in options.defines:
            d = define.split('=')
            if len(d) == 1:
                config.defines[d[0]] = ''
            else:
                config.defines[d[0]] = '='.join(d[1:])

    import reader, writer
    
    try:
        read_ok = reader.read(args[0])
    finally:
        if xmlparser.cache != None:
            xmlparser.cache.close()
            xmlparser.cache = None

    if not read_ok:
        sys.exit(1)

    if options.dump:
        import mk_dump
        mk_dump.dumpMakefile()
    else: 
        if not writer.write():
            sys.exit(1)

    if config.track_deps:
        import dependencies
        dependencies.save(config.deps_file)

if __name__ == '__main__':
    if sys.version_info[0:3] < (2,3,0):
        sys.stderr.write('error: Bakefile requires at least Python 2.3.0\n')
        sys.exit(1)

    do_profiling = 0 # set to 1 if debugging bottlenecks
    
    try:
        if do_profiling:
            import hotshot
            prof = hotshot.Profile('bakefile.prof')
            prof.runcall(run, sys.argv[1:])
            prof.close()
        else:
            run(sys.argv[1:])    
    except errors.ErrorBase, e:
        sys.stderr.write('%s\n' % e)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.stderr.write('\nerror: bakefile cancelled by user\n')
        sys.exit(2)
