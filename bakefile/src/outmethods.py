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
        order = ['']
        for line in data:
            pos = line.find(BLOCK_MARK_LEFT)
            if pos != -1:
                l = line.rstrip()
                if l.endswith(BLOCK_MARK_RIGHT):
                    name = l[pos+len(BLOCK_MARK_LEFT):-len(BLOCK_MARK_RIGHT)]
                    cur = []
                    blocks[name] = cur
                    order.append(name)
            cur.append(line)
        return blocks, order

    b_old, order_old = findBlocks(old)
    b_new, order_new = findBlocks(new)

    out = []
    for block in order_old:
        if block in b_new:
            out += b_new[block]
            del b_new[block]
            order_new.remove(block)
        else:
            out += b_old[block]

    for block in order_new:
        out += b_new[block]
   
    return out
