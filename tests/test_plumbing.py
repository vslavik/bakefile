#
#  This file is part of Bakefile (http://www.bakefile.org)
#
#  Copyright (C) 2008-2012 Vaclav Slavik
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

"""
Misc tests of Bakefile's internals' correctness.
"""

import os.path
import copy

import bkl.interpreter
import bkl.dumper
import bkl.io

import projects
projects_dir = os.path.dirname(projects.__file__) 


def test_model_deepcopy():
    i = bkl.interpreter.Interpreter()
    i.process_file(os.path.join(projects_dir, 'submodules', 'main.bkl'))
    model = i.model
    model_copy = copy.deepcopy(model)
    model_txt = bkl.dumper.dump_project(model)
    model_copy_txt = bkl.dumper.dump_project(model_copy)
    assert model_txt == model_copy_txt


def test_file_io_unix(tmpdir):
    p = tmpdir.join("textfile")
    f = bkl.io.OutputFile(str(p), bkl.io.EOL_UNIX)
    f.write("one\ntwo\n")
    f.commit()
    text_read = p.read("rb")
    assert text_read == "one\ntwo\n"

def test_file_io_win(tmpdir):
    p = tmpdir.join("textfile")
    f = bkl.io.OutputFile(str(p), bkl.io.EOL_WINDOWS)
    f.write("one\ntwo\n")
    f.commit()
    text_read = p.read("rb")
    assert text_read == "one\r\ntwo\r\n"
