#
# Output methods
#
# $Id$
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

