#
#  This file is part of Bakefile (http://www.bakefile.org)
#
#  Copyright (C) 2008-2009 Vaclav Slavik
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

import bakefile.parser, bakefile.interpreter, bakefile.error
import dumper

import os, os.path
from glob import glob


def test_interpreter():
    """
    Tests Bakefile parser and compares resulting model with a copy saved
    in .model file. Does this for all .bkl files under tests/parser directory.
    """
    import test_parsing
    d = os.path.dirname(test_parsing.__file__)
    for f in glob("%s/*/*.bkl" % d):
        yield _test_interpreter_on_file, d, str(f)


def _test_interpreter_on_file(testdir, input):
    assert input.startswith(testdir)
    f = input[len(testdir)+1:]
    cwd = os.getcwd()
    os.chdir(testdir)
    try:
        _do_test_interpreter_on_file(f)
    finally:
        os.chdir(cwd)

def _do_test_interpreter_on_file(input):
    print 'interpreting %s' % input

    try:
        t = bakefile.parser.parse_file(input)
        i = bakefile.interpreter.Interpreter(t)
        model = i.create_model()
        as_text = dumper.dump_model(model)
    except bakefile.error.Error, e:
        as_text = "ERROR:\n%s" % e
    print """
created model:
---
%s
---
""" % as_text

    model_file = os.path.splitext(input)[0] + '.model'
    expected = file(model_file, "rt").read().strip()
    print """
expected model:
---
%s
---
""" % expected

    assert as_text == expected
