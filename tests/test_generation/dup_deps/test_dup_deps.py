#  This file is part of Bakefile (http://bakefile.org)
#
#  Copyright (C) 2018 Vadim Zeitlin
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
import bkl.parser, bkl.interpreter, bkl.error
from indir import in_directory

def test_dup_deps():
    with in_directory(os.path.dirname(__file__)):
        t = bkl.parser.parse_file('dup_deps.bkl')
        i = bkl.interpreter.Interpreter()
        i.process(t)

        with open('dup_deps.sln', "rt") as sln:
            # Find the number of dependencies for the project (we rely on
            # there being only a single dependencies section).
            num_deps = 0
            inside_deps = False
            for line in sln.readlines():
                if inside_deps:
                    if 'EndProjectSection' in line:
                        break

                    num_deps += 1
                elif 'ProjectSection(ProjectDependencies)' in line:
                    inside_deps = True

            # The dependency should only be counted once, even if it's
            # mentioned twice in the input bakefile.
            assert num_deps == 1
