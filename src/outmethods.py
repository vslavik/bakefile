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
#  Output methods
#

import errors

def mergeBlocks(old, new):

    def findBlocks(data):
        BLOCK_MARK_LEFT = '### begin block '
        BLOCK_MARK_RIGHT = ' ###'
        blocks = {}
        cur = []
        blocks[''] = cur
        for line in data:
            pos = line.find(BLOCK_MARK_LEFT)
            if pos != -1:
                l = line.rstrip()
                if l.endswith(BLOCK_MARK_RIGHT):
                    name = l[pos+len(BLOCK_MARK_LEFT):-len(BLOCK_MARK_RIGHT)]
                    cur = []
                    blocks[name] = cur
            cur.append(line)
        return blocks
    b_old = findBlocks(old)
    b_new = findBlocks(new)

    keys = b_old.keys() + b_new.keys()
    keys.sort()
    
    out = []
    used = {}
    for block in keys:
        if block in used: continue
        if block in b_new:
            out += b_new[block]
            used[block] = 1
        else:
            out += b_old[block]
            used[block] = 1
   
    return out


def insertBetweenMarkers(old, new):
    """Inserts text between markers (= special meaning lines). 'old' must
       contain firsts and last line of 'new' -- the text between them is
       replaced with 'new'."""

    begin = new[0]
    end = new[-1]

    if (begin not in old) or (end not in old):
        raise errors.Error('markers not present in the file')

    out = []
    i = 0
    while i < len(old) and old[i] != begin:
        out.append(old[i])
        i += 1
    while i < len(old) and old[i] != end: i += 1
    i += 1
    out += new
    while i < len(old):
        out.append(old[i])
        i += 1

    return out

