#!/usr/bin/env python

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

BAKEFILE_VERSION = "0.2.1"

import sys, os.path
try:
    from optparse import OptionParser
except ImportError:
    from optik import OptionParser

import formats

def addIncludePaths(includes):
    import config
    for p in includes:
        config.searchPath.append(os.path.normpath(p))

class BakefileOptionParser(OptionParser):
    def __init__(self):
        OptionParser.__init__(self,
                              version='Bakefile %s' % BAKEFILE_VERSION,
                              usage='usage: %prog [options] inputfile.bkl')
    def print_help(self, file=None):
        if file is None:
            file = sys.stdout
        OptionParser.print_help(self, file)
   
        # show all available formats:
        if self.values.includes != None:
            addIncludePaths(self.values.includes)
        file.write('\n%s' % formats.showFormats())


def run(args):
    import reader, writer
    import config

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
        sys.exit(1)

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
            import xmlparser, pickle, shelve
            xmlparser.cache = shelve.open(options.xml_cache,
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
    
    config.defines = {}
    if options.defines != None:
        for define in options.defines:
            d = define.split('=')
            if len(d) == 1:
                config.defines[d[0]] = ''
            else:
                config.defines[d[0]] = '='.join(d[1:])
    
    if not reader.read(args[0]):
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
    if sys.version_info[0:3] < (2,2,2):
        sys.stderr.write('error: Bakefile requires at least Python 2.2.2\n')
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
    except KeyboardInterrupt:
        sys.stderr.write('\nerror: bakefile cancelled by user\n')
        sys.exit(1)
