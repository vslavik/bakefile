#
#  This file is part of Bakefile (http://bakefile.sourceforge.net)
#
#  Copyright (C) 2003,2004 Vaclav Slavik
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License version 2 as
#  published by the Free Software Foundation.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
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
