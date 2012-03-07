#
#  This file is part of Bakefile (http://www.bakefile.org)
#
#  Copyright (C) 2012 Vaclav Slavik
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

# Grep-friendly version string
VERSION="1.0.1"

def get_version():
    # check to see if we're running from a git checkout and report more exact
    # version if we do:
    import os.path
    gitdir = os.path.join(os.path.dirname(__file__), "../../.git")
    if os.path.isdir(gitdir):
        import subprocess
        try:
            ver = subprocess.check_output(["git", "--git-dir=%s" % gitdir, "describe"])
            ver = ver.strip()
            if ver:
                if ver[0] == "v": ver = ver[1:]
                ver = ver.split("-")
                if len(ver) > 1:
                    return "%s-%s" % (ver[0], ver[1])
                else:
                    return ver[0]
        # fall back to normal version information in case of any error
        # (e.g. missing git, problem running git, Python 2.6 w/o check_output):
        except Exception:
            pass
    return VERSION
