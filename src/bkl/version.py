#
#  This file is part of Bakefile (http://bakefile.org)
#
#  Copyright (C) 2012-2018 Vaclav Slavik
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
VERSION="1.2.5.1"

def get_version():
    # check to see if we're running from a git checkout and report more exact
    # version if we do:
    import os.path
    gitdir = os.path.join(os.path.dirname(__file__), "../../.git")
    # notice that we intentionally use exists() and not isdir() as this git
    # "directory" is actually a file inside a git submodule
    if os.path.exists(gitdir):
        import subprocess
        try:
            ver = subprocess.check_output(["git", "--git-dir=%s" % gitdir, "describe"]).strip()
            if ver:
                if ver[0] == "v": ver = ver[1:]
                version_fields = ver.split("-")
                version = version_fields[0]
                if len(version_fields) > 1:
                    # if we're using a 2 component version, transform it
                    # into 3 component one to ensure that versions are
                    # compared correctly: we want to have
                    #
                    #       1.2 < 1.2-git < 1.2.1
                    #
                    # so the 2nd git version after 1.2 must be "1.2.0.2"
                    # and not just "1.2.2" which wouldn't compare correctly
                    if len(version.split(".")) < 3: version += ".0"
                    return "%s-%s" % (version, version_fields[1])
                else:
                    return version
        # fall back to normal version information in case of any error
        # (e.g. missing git or problem running it):
        except Exception:
            pass
    return VERSION


def get_version_tuple(version_str=None):
    if version_str is None:
        version_str = get_version()
    import re
    components = re.split(r'[.-]', version_str)
    return tuple(int(x) for x in components)


def check_version(required):
    """
    Checks if given version requirement is satisfied and throws if not."
    """
    bkl_ver = get_version_tuple()
    try:
        req_ver = get_version_tuple(required)
    except ValueError:
        from bkl.error import ParserError
        raise ParserError("invalid version number \"%s\"" % required)

    if bkl_ver < req_ver:
        from bkl.error import VersionError
        raise VersionError("Bakefile version >= %s is required (you have %s)" %
                           (required, get_version()))
