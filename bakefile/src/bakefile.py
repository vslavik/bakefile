#!/usr/bin/env python
# $Id$

BAKEFILE_VERSION = "0.1.1"

import sys

def run(args):
    import reader, writer
    import config
    from optik import OptionParser

    parser = OptionParser(version='Bakefile %s' % BAKEFILE_VERSION,
                          usage='usage: %prog [options] inputfile.bkl')
    parser.add_option('-f', '--format',
                      action="store", dest='format',
                      help='format of generated makefile')
    parser.add_option('-o', '--output',
                      action="store", dest='outfile',
                      help='output file')
    parser.add_option('-D',
                      action="append", dest='defines', metavar='VAR=VALUE',
                      help='override variable or option definition')
    parser.add_option('-v', '--verbose',
                      action="store_true", dest='verbose', default=0,
                      help='display detailed information')
    parser.add_option('', '--dump',
                      action="store_true", dest='dump', default=0,
                      help='dump parsed makefile content instead of '+
                           'generating makefile')

    options, args = parser.parse_args(args)

    if len(args) != 1:
        parser.error('incorrect number of arguments')
        sys.exit(1)

    config.verbose = options.verbose
    config.format = options.format # FIXME -- check for validity
    config.output_file = options.outfile
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

if __name__ == '__main__':
    run(sys.argv[1:])
