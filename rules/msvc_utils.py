
# Helper functions for 'msvc6prj' format:
#
# $Id$

def formatDefine(value):
    if value == '':
        return ''
    if '=' in value:
        return '/D %s' % value
    return '/D "%s"' % value
