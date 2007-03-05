#
#  This file is part of Bakefile (http://www.bakefile.org)
#
#  Copyright (C) 2003-2007 Vaclav Slavik
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
#  $Id$
#
#  Dumps parsed bakefiles content
#

import mk

def dumpMakefile():
    print '\nVariables:'
    for v in mk.vars:
        print '  %-30s = %s' % (v, mk.vars[v])

    print '\nOptions:'
    for o in mk.options.values():
        print '  %-30s (default:%s,values:%s)' % (o.name, o.default, o.values)

    print '\nConditions:'
    for c in mk.conditions.values():
        print '  %-30s (%s)' % (c.name,c.exprs)

    print '\nConditional variables:'
    for v in mk.cond_vars.values():
        print '  %-30s' % v.name
        for vv in v.values:
            print '    if %-25s = %s' % (vv.cond.name, vv.value)

    print '\nTargets:'
    for t in mk.targets.values():
        print '  %s %s' % (t.type, t.id)
        for v in t.vars:
            print '    %-28s = %s' % (v, t.vars[v])
