#
# Output methods
#
# $Id$
#

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
