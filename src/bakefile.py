#!/usr/bin/env python
# $Id$

BAKEFILE_VERSION = "0.1.1"

import sys, os.path
from optik import OptionParser
import formats

class BakefileOptionParser(OptionParser):
    def __init__(self):
        OptionParser.__init__(self,
                              version='Bakefile %s' % BAKEFILE_VERSION,
                              usage='usage: %prog [options] inputfile.bkl')
    def print_help(self, file=None):
        if file is None:
            file = sys.stdout
        OptionParser.print_help(self, file)
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
    parser.add_option('', '--output-deps',
                      action="store", dest='deps_file', metavar='DEPSFILE',
                      help="output dependencies information for bakefile_gen")
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
    
    if options.includes != None:
        for p in options.includes:
            config.searchPath.append(os.path.normpath(p))

    formats.loadFormats()
    if options.format == None:
        parser.error('you must specify output format (use -f option)')
    config.format = options.format
    if not formats.isValidFormat(config.format):
        parser.error('invalid format\n\n' + formats.showFormats())

    if options.deps_file != None:
        config.track_deps = 1
        config.deps_file = options.deps_file
    
    if options.outfile != None:
        config.output_file = options.outfile
    else:
        fmt = formats.formats[config.format]
        if fmt.defaultFile == None or fmt.defaultFile == '':
            parser.error('you must specify output file (use -o option)')
        else:
            config.output_file = \
                os.path.join(os.path.dirname(args[0]), fmt.defaultFile)

    config.verbose = options.verbose
    config.debug = options.debug
    
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
    try:
        run(sys.argv[1:])
    except KeyboardInterrupt:
        sys.stderr.write('\nerror: bakefile cancelled by user\n')
        sys.exit(1)
