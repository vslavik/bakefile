#!/usr/bin/env python
#
#  This file is part of Bakefile (http://bakefile.org)
#
#  Copyright (C) 2009-2013 Vaclav Slavik
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

import sys
import logging
from optparse import OptionParser, OptionGroup
from time import time

# This is needed to initialize colored output on Windows. It must be done
# before any stdout is done.
try:
    import clint.packages.colorama
    clint.packages.colorama.init()
except ImportError:
    pass

class BklFormatter(logging.Formatter):

    def __init__(self):
        logging.Formatter.__init__(self, fmt=logging.BASIC_FORMAT)
        try:
            from clint.textui import colored
            self.format_warning = colored.yellow
            self.format_error = colored.red
        except ImportError:
            self.format_warning = lambda x: x
            self.format_error = lambda x: x

    def format(self, record):
        level = record.levelno
        if level == logging.ERROR or level == logging.WARNING or level == logging.INFO:
            msg = ""
            if hasattr(record, "pos") and record.pos:
                msg = "%s: " % record.pos
            if level != logging.INFO:
                msg += "%s: " % record.levelname.lower()
            msg += record.getMessage()
            if level == logging.ERROR:
                msg = self.format_error(msg)
            elif level == logging.WARNING:
                msg = self.format_warning(msg)
            return msg
        else:
            return logging.Formatter.format(self, record)

logger = logging.getLogger()
log_handler = logging.StreamHandler()
log_handler.setFormatter(BklFormatter())
logger.addHandler(log_handler)

# OptionParser only allows a string version argument, it can't be a callback.
# That's too bad, because it's too early to import bkl.version now, it would
# import bkl too and we don't have debug logging set up yet (see the comments
# below as well). This class delays import until --version is actually used.
# TODO-PY26: Use 2.7's argparse module and get rid of this hack
class BklOptionParser(OptionParser):
    def get_version(self):
        import bkl.version
        return "bakefile %s" % bkl.version.get_version()

parser = BklOptionParser(version="bakefile")
parser.add_option(
        "-v", "--verbose",
        action="store_true", dest="verbose", default=False,
        help="show verbose output")
parser.add_option(
        "", "--dry-run",
        action="store_true", dest="dry_run", default=False,
        help="don't write any files, just pretend to do it")
parser.add_option(
        "", "--diff-only",
        action="store_true", dest="diff_only", default=False,
        help="only output diffs instead of modiyfing the files, implies --dry-run")
parser.add_option(
        "", "--force",
        action="store_true", dest="force", default=False,
        help="touch output files even if they're unchanged")
parser.add_option(
        "-t", "--toolset",
        action="append", dest="toolsets",
        metavar="TOOLSET",
        help="only generate files for the given toolset (may be specified more than once)")

debug_group = OptionGroup(parser, "Debug Options")
debug_group.add_option(
        "", "--debug",
        action="store_true", dest="debug", default=False,
        help="show debug log")
debug_group.add_option(
        "", "--dump-model",
        action="store_true", dest="dump", default=False,
        help="dump project's model to stdout instead of generating output")
debug_group.add_option(
        "", "--dump-model-for",
        action="store", dest="dump_toolset", default=False,
        metavar="TOOLSET",
        help="like --dump-model, but with toolset-optimized model")
parser.add_option_group(debug_group)

options, args = parser.parse_args(sys.argv[1:])

if len(args) != 1:
    sys.stderr.write("incorrect number of arguments, exactly 1 .bkl required\n")
    sys.exit(3)

if options.debug:
    log_level = logging.DEBUG
elif options.verbose:
    log_level = logging.INFO
else:
    log_level = logging.WARNING
logger.setLevel(log_level)

if options.diff_only and options.force:
    sys.stderr.write("--diff-only and --force option can't be used together\n")
    sys.exit(3)

# note: we intentionally import bakefile this late so that the logging
# module is already initialized
import bkl.error
from bkl.interpreter import Interpreter
import bkl.dumper
import bkl.io

try:
    start_time = time()
    bkl.io.dry_run = options.dry_run
    bkl.io.diff_only = options.diff_only
    bkl.io.force_output = options.force
    if options.dump:
        intr = bkl.dumper.DumpingInterpreter()
    elif options.dump_toolset:
        intr = bkl.dumper.DumpingInterpreter(options.dump_toolset)
    else:
        intr = Interpreter()
    if options.toolsets:
        intr.limit_toolsets(options.toolsets)
    intr.process_file(args[0])
    logger.info("created files: %d, updated files: %d (time: %.1fs)",
                bkl.io.num_created, bkl.io.num_modified, time() - start_time)

except KeyboardInterrupt:
    if options.debug:
        raise
    else:
        sys.exit(2)
except IOError as e:
    if options.debug:
        raise
    else:
        logging.error(e)
        sys.exit(1)
except bkl.error.Error as e:
    if options.debug:
        raise
    else:
        logging.error(e.msg, extra={"pos":e.pos})
        sys.exit(1)
