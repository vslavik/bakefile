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

import bkl.parser, bkl.error
from indir import in_directory

def do_get_testdir():
    import test_parsing
    return os.path.dirname(test_parsing.__file__)

@pytest.fixture(scope='session')
def testdir():
    return do_get_testdir()

def ast_filenames():
    """
    This fixture returns the list of all .bkl files under tests/parser
    directory that have a matching .ast present.
    """
    return [str(f) for f in glob("%s/*/*.ast" % do_get_testdir())]

@pytest.mark.parametrize('ast_file', ast_filenames())
def test_parser(testdir, ast_file):
    """
    Tests Bakefile parser and compares resulting AST with a copy saved
    in .ast file.
    """
    assert ast_file.startswith(testdir)

    input = os.path.splitext(ast_file)[0] + '.bkl'

    f = input[len(testdir)+1:]
    with in_directory(testdir):
        _do_test_parser_on_file(f, ast_file)


def _do_test_parser_on_file(input, ast_file):
    print 'parsing %s' % input

    try:
        t = bkl.parser.parse_file(input)
        as_text = t.toStringTree()
    except bkl.error.Error, e:
        as_text = "ERROR:\n%s" % str(e).replace("\\", "/")
    print """
parsed tree:
---
%s
---
""" % as_text

    expected = file(ast_file, "rt").read().strip()
    print """
expected tree:
---
%s
---
""" % expected

    assert as_text == expected


def test_parsing_bakefile_0_2_xml():
    import test_parsing
    d = os.path.dirname(test_parsing.__file__)
    with pytest.raises(bkl.error.ParserError):
        bkl.parser.parse_file(os.path.join(d, "bakefile_0_2.bkl"))

def test_parsing_old_version():
    import test_parsing
    d = os.path.dirname(test_parsing.__file__)
    with pytest.raises(bkl.error.VersionError):
        bkl.parser.parse_file(os.path.join(d, "version_old.bkl"))

def test_parsing_very_old_version():
    import test_parsing
    d = os.path.dirname(test_parsing.__file__)
    with pytest.raises(bkl.error.VersionError):
        bkl.parser.parse_file(os.path.join(d, "version_very_old.bkl"))
