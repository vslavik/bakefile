#!/usr/bin/env python

# Merges helper scripts into bakefile.m4
#
# $Id$

MARK_IDENT = 'dnl ===================== '
MARK_BEGINS = ' begins here ====================='
MARK_ENDS = ' ends here ====================='

import re

def mergeFile(filename):
    f = open(filename, 'rt').readlines()
    f2 = []
    for i in f:
        i = re.sub(r'\$', r'${D}', i)
        i = re.sub(r'([][])', r'[\1]', i)
        i = re.sub(r'`', r'\`', i)
        i = re.sub(r'@([a-zA-Z0-9_]+)@', r'${\1}', i)
        f2.append(i)
    return f2

bk = open('bakefile.m4', 'rt').readlines()
bk2 = []
i = 0
while i < len(bk):
    line = bk[i]
    bk2.append(line)
    if (line.startswith(MARK_IDENT) and line.strip().endswith(MARK_BEGINS)):
        filename = line[len(MARK_IDENT):-len(MARK_BEGINS)-1]
        print 'merging %s...' % filename
        bk2.append("D='$'\n")
        bk2.append('cat <<EOF >%s\n' % filename)
        bk2 += mergeFile(filename)
        bk2.append('EOF\n')
        i += 1
        while not (bk[i].startswith(MARK_IDENT) and
                   bk[i].strip().endswith(MARK_ENDS)):
            i += 1
        bk2.append(bk[i])
    i += 1

open('bakefile.m4~', 'wt').writelines(bk)
open('bakefile.m4', 'wt').writelines(bk2)
