# -*- coding: utf-8 -*-
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
import pytest
from glob import glob

import bkl.parser, bkl.interpreter, bkl.error
import bkl.dumper

from indir import in_directory

def do_get_testdir():
    import projects
    return os.path.dirname(projects.__file__)

@pytest.fixture(scope='session')
def testdir():
    return do_get_testdir()

def project_filenames():
    """
    This function returns the list of all .bkl files under tests/projects
    directory.
    """
    return ([str(f) for f in glob("%s/*.bkl" % do_get_testdir())] +
            [str(f) for f in glob("%s/*/*.bkl" % do_get_testdir())])

class InterpreterForTestSuite(bkl.interpreter.Interpreter):
    def generate(self):
        # dump the model first, because generate() further modifies
        # it by doing per-toolset changes:
        self.dumped_model = bkl.dumper.dump_project(self.model)
        # then let the generator do its magic
        super(InterpreterForTestSuite, self).generate()


@pytest.mark.parametrize('project_file', project_filenames())
def test_full(testdir, project_file):
    """
    Fully tests Bakefile interpreter and compares resulting model with a copy
    saved in .model file, as well as with all the generated files.
    """
    assert project_file.startswith(testdir)

    model_file = os.path.splitext(project_file)[0] + '.model'

    f = project_file[len(testdir)+1:]
    with in_directory(testdir):
        _do_test_on_file(f, model_file)

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

def test_unicode_filename():
    """
    This test checks that filenames relative to a directory containing
    non-ASCII characters work correctly, see
    https://github.com/vslavik/bakefile/issues/96
    """
    t = bkl.parser.parse("""
toolsets = gnu;
program progname {
    sources { ../relpath.c }
}
""", "test.bkl")
    i = InterpreterForTestSuite()

    import shutil
    import tempfile
    cwd = os.getcwd()
    tmpdir = tempfile.mkdtemp(prefix=u"Üñîçöḍè".encode('utf-8'))
    try:
        with in_directory(tmpdir):
            i.process(t)
    finally:
        shutil.rmtree(tmpdir)
