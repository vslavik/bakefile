
import os, os.path, sys

# Be verbose:
verbose = 0

# Directories where makefiles are looked for:
searchPath = os.getenv('BAKEFILE_PATHS', '').split(os.pathsep)
if searchPath == ['']: searchPath = []
searchPath.append(
             os.path.normpath(os.path.join(
             os.path.dirname(os.path.realpath(sys.argv[0])), '..', 'rules')))
searchPath.append(
             os.path.normpath(os.path.join(
             os.path.dirname(os.path.realpath(sys.argv[0])), '..', 'output')))

# The way target makefiles quote variables:
variableSyntax = '$(%s)' # FIXME

# Output format:
format = None

# List of parsed output directives ((file,writer) tuples):
to_output = []
