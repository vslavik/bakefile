
# Helper functions for 'msvc6prj' format:
#
# $Id$

def formatFlag(value, flag):
    if value == '':
        return ''
    if '=' in value:
        return '%s %s' % (flag, value)
    return '%s "%s"' % (flag, value)

def formatDefine(value):
    return formatFlag(value, '/D')

def formatInclude(value):
    return formatFlag(value, '/I')
