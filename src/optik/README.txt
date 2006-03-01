Optik 1.4
=========

Optik is a powerful, flexible, extensible, easy-to-use command-line
parsing library for Python.  Using Optik, you can add intelligent,
sophisticated handling of command-line options to your scripts with very
little overhead.

Here's an example of using Optik to add some command-line options to a
simple script:

  from optik import OptionParser
  [...]
  parser = OptionParser()
  parser.add_option("-f", "--file", dest="filename",
                    help="write report to FILE", metavar="FILE")
  parser.add_option("-q", "--quiet",
                    action="store_false", dest="verbose", default=1,
                    help="don't print status messages to stdout")

  (options, args) = parser.parse_args()

With these few lines of code, users of your script can now do the
"usual thing" on the command-line:

  <yourscript> -f outfile --quiet
  <yourscript> -qfoutfile
  <yourscript> --file=outfile -q
  <yourscript> --quiet --file outfile

(All of these result in
  options.filename == "outfile"
  options.verbose == 0
...just as you might expect.)

Even niftier, users can run one of
  <yourscript> -h
  <yourscript> --help
and Optik will print out a brief summary of your script's options:

  usage: <yourscript> [options]

  options:
    -h, --help           show this help message and exit
    -fFILE, --file=FILE  write report to FILE
    -q, --quiet          don't print status messages to stdout

That's just a taste of the flexibility Optik gives you in parsing your
command-line.  See the documentation included in the package for
details.


REQUIREMENTS & INSTALLATION
---------------------------
        
Optik requires Python 2.0 or greater.

Installing Optik is easy; just use the standard incantion for installing
Python modules:
  python setup.py install


TESTING
-------

Optik comes with some simple test scripts.  To run them before installing
Optik, try this (under Unix):
  python setup.py build
  env PYTHONPATH=`pwd`/build/lib ./test/runall
(Adjust to taste for your OS.)

If all is well, each test script will print "ok: N" (where N is an
integer) for each test in the test script.  If anything goes wrong, the
test script will crash and/or print "not ok".


DOCUMENTATION
-------------

Optik comes with several documents:

  * tao.txt       philosophy and background; if you're not sure what the
                  difference between an argument and an option is, read this

  * basic.txt     basic information on using Optik in your programs

  * advanced.txt  a detailed reference guide to all of Optik's features

  * callbacks.txt how to define callback options and write the callback
                  functions that go with them

  * extending.txt information on extending Optik (eg. how to add new
                  actions and types)

Additionally, the examples/ subdirectory demonstrates various ways to
extend Optik.


MAILING LISTS
-------------

The optik-users@lists.sourceforge.net list exists for general discussion
of Optik.  To join or view the list archive, visit

  http://lists.sourceforge.net/lists/listinfo/optik-users

General questions about Optik should be addressed to the list:
  optik-users@lists.sourceforge.net

(Currently, you don't have to be a member to post.)

If you want to follow the bleeding edge of Optik development, you can
join the optik-checkins list:

  http://lists.sourceforge.net/lists/listinfo/optik-checkins


AUTHOR, COPYRIGHT, AVAILABILITY
-------------------------------

The latest version of Optik can be found at
  http://optik.sourceforge.net/

Optik was written by Greg Ward <gward@python.net> with major
contributions by David Goodger and smaller contributions by:

  Matthew Mueller
  Terrel Shumway

Copyright (c) 2001-2002 Gregory P. Ward.  All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are
met:

  * Redistributions of source code must retain the above copyright
    notice, this list of conditions and the following disclaimer.

  * Redistributions in binary form must reproduce the above copyright
    notice, this list of conditions and the following disclaimer in the
    documentation and/or other materials provided with the distribution.
    
  * Neither the name of the author nor the names of its
    contributors may be used to endorse or promote products derived from
    this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS
IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED
TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A
PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE AUTHOR OR
CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
