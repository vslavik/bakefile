#
#  This file is part of Bakefile (http://bakefile.org)
#
#  Copyright (C) 2008-2013 Vaclav Slavik
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

import os, os.path
from glob import glob

import bkl.parser, bkl.interpreter, bkl.error
import bkl.dumper


def test_full():
    """
    Fully tests Bakefile interpreter and compares resulting model with a copy
    saved in .model file, as well as with all the generated files. Does this
    for all .bkl files under tests/projects directory that have a model dump
    present.
    """
    import projects
    d = os.path.dirname(projects.__file__)
    for f in glob("%s/*.bkl" % d):
        yield _test_on_file, d, str(f)
    for f in glob("%s/*/*.bkl" % d):
        yield _test_on_file, d, str(f)


class InterpreterForTestSuite(bkl.interpreter.Interpreter):
    def generate(self):
        # dump the model first, because generate() further modifies
        # it by doing per-toolset changes:
        self.dumped_model = bkl.dumper.dump_project(self.model)
        # then let the generator do its magic
        super(InterpreterForTestSuite, self).generate()


def _test_on_file(testdir, project_file):
    assert project_file.startswith(testdir)

    model_file = os.path.splitext(project_file)[0] + '.model'

    f = project_file[len(testdir)+1:]
    cwd = os.getcwd()
    os.chdir(testdir)
    try:
        _do_test_on_file(f, model_file)
    finally:
        os.chdir(cwd)

def _do_test_on_file(input, model_file):
    print 'interpreting %s' % input

    try:
        t = bkl.parser.parse_file(input)
        i = InterpreterForTestSuite()
        i.process(t)
        as_text = i.dumped_model
    except bkl.error.Error, e:
        as_text = "ERROR:\n%s" % str(e).replace("\\", "/")
    print """
created model:
---
%s
---
""" % as_text

    expected = file(model_file, "rt").read().strip()
    print """
expected model:
---
%s
---
""" % expected

    assert as_text == expected
