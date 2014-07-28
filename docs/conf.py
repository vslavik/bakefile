# -*- coding: utf-8 -*-
#
# Bakefile documentation build configuration file, created by
# sphinx-quickstart on Mon Oct  6 10:56:38 2008.
#
# This file is execfile()d with the current directory set to its containing dir.
#
# The contents of this file are pickled, so don't put values in the namespace
# that aren't pickleable (module imports are okay, they're removed automatically).
#
# All configuration values have a default value; values that are commented out
# serve to show the default value.

import sys, os, subprocess

# Check if Sphinx is running on readthedocs.org
on_rtd = os.environ.get('READTHEDOCS', None) == 'True'

# If your extensions are in another directory, add it here. If the directory
# is relative to the documentation root, use os.path.abspath to make it
# absolute, like shown here.
sys.path.append(os.path.abspath('../src'))
sys.path.append(os.path.abspath('.'))

import bkl.version


# General configuration
# ---------------------

# Add any Sphinx extension module names here, as strings. They can be extensions
# coming with Sphinx (named 'sphinx.ext.*') or your custom ones.
extensions = ['sphinx.ext.autodoc']

# Add any paths that contain templates here, relative to this directory.
templates_path = ['.templates']

# The suffix of source filenames.
source_suffix = '.rst'

# The master toctree document.
master_doc = 'index'

# General substitutions.
project = 'Bakefile'
copyright = '2009-2013 Vaclav Slavik'

# The default replacements for |version| and |release|, also used in various
# other places throughout the built documents.
#
# The short X.Y version.
version = '%d.%d' % bkl.version.get_version_tuple()[0:2]
# The full version, including alpha/beta/rc tags.
release = bkl.version.get_version()

# There are two options for replacing |today|: either, you set today to some
# non-false value, then it is used:
#today = ''
# Else, today_fmt is used as the format for a strftime call.
today_fmt = '%B %d, %Y'

# List of documents that shouldn't be included in the build.
#unused_docs = []

# List of directories, relative to source directories, that shouldn't be searched
# for source files.
#exclude_dirs = []

# The reST default role (used for this markup: `text`) to use for all documents.
#default_role = None

# If true, '()' will be appended to :func: etc. cross-reference text.
add_function_parentheses = True

# If true, the current module name will be prepended to all description
# unit titles (such as .. function::).
#add_module_names = True

# If true, sectionauthor and moduleauthor directives will be shown in the
# output. They are ignored by default.
#show_authors = False

# The name of the Pygments (syntax highlighting) style to use.
# pygments_style = 'sphinx'
# highlight_language = 'bkl'

from sphinx.highlighting import lexers
from bkl_lexer import BakefileLexer
lexers['bkl'] = BakefileLexer()


# Options for HTML output
# -----------------------

# The style sheet to use for HTML and HTML Help pages. A file of that name
# must exist either in Sphinx' static/ path, or in one of the custom paths
# given in html_static_path.
if not on_rtd:
    html_theme = 'haiku'


# The name for this set of Sphinx documents.  If None, it defaults to
# "<project> v<release> documentation".
#html_title = None

# A shorter title for the navigation bar.  Default is the same as html_title.
#html_short_title = None

# The name of an image file (within the static path) to place at the top of
# the sidebar.
#html_logo = None

# The name of an image file (within the static path) to use as favicon of the
# docs.  This file should be a Windows icon file (.ico) being 16x16 or 32x32
# pixels large.
#html_favicon = None

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['.static']

# If not '', a 'Last updated on:' timestamp is inserted at every page bottom,
# using the given strftime format.
html_last_updated_fmt = '%b %d, %Y'

# If true, SmartyPants will be used to convert quotes and dashes to
# typographically correct entities.
#html_use_smartypants = True

# Custom sidebar templates, maps document names to template names.
#html_sidebars = {}

# Additional templates that should be rendered to pages, maps page names to
# template names.
#html_additional_pages = {}

# If false, no module index is generated.
#html_use_modindex = True

# If false, no index is generated.
#html_use_index = True

# If true, the index is split into individual pages for each letter.
#html_split_index = False

# If true, the reST sources are included in the HTML build as _sources/<name>.
#html_copy_source = True

# If true, an OpenSearch description file will be output, and all pages will
# contain a <link> tag referring to it.  The value of this option must be the
# base URL from which the finished HTML is served.
#html_use_opensearch = ''

# If nonempty, this is the file name suffix for HTML files (e.g. ".xhtml").
#html_file_suffix = ''

# Output file base name for HTML help builder.
htmlhelp_basename = 'Bakefiledoc'


autodoc_member_order = "groupwise"
autoclass_content = "both"

# TODO: replace this with autodoc_mock_imports once Sphinx 1.3 is released
# see https://read-the-docs.readthedocs.org/en/latest/faq.html#i-get-import-errors-on-libraries-that-depend-on-c-modules
MOCK_MODULES = ['bkl.parser.BakefileLexer', 'bkl.parser.BakefileParser',
                'bkl.parser.BakefileQuotedStringLexer', 'bkl.parser.BakefileQuotedStringParser']

class Mock(object):
    __all__ = []
    def __init__(self, *args, **kwargs):
        pass
    def __call__(self, *args, **kwargs):
        return Mock()
    @classmethod
    def __getattr__(cls, name):
        if name in ('__file__', '__path__'):
            return '/dev/null'
        elif name[0] == name[0].upper():
            mockType = type(name, (), {})
            mockType.__module__ = __name__
            return mockType
        else:
            return Mock()

for mod_name in MOCK_MODULES:
    sys.modules[mod_name] = Mock()

subprocess.call(os.path.abspath('gen_reference.py'), shell = True)
