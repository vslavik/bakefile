#!/usr/bin/env python

import sys
import os.path

if len(sys.argv) != 4:
    raise RuntimeError("invalid arguments, usage: %s --<both|header|source> output input" % sys.argv[0])

def gen_header(outname):
    dirname, basename = os.path.split(outname)
    name, ext = os.path.splitext(basename)
    with file(os.path.join(dirname, name + ".h"), "wt") as outf:
        outf.write("extern const char *get_%s_body();\n" % name)

def gen_source(outname, msg):
    dirname, basename = os.path.split(outname)
    name, ext = os.path.splitext(basename)
    with file(os.path.join(dirname, name + ".cpp"), "wt") as outf:
        with file(msg, "rt") as inpf:
            outf.write("const char *get_%s_body() { return \"" % name + inpf.read().rstrip('\n') + "\"; }\n")

if sys.argv[1] == "--both":
    gen_header(sys.argv[2])
    gen_source(sys.argv[2], sys.argv[3])
elif sys.argv[1] == "--header":
    gen_header(sys.argv[2])
elif sys.argv[1] == "--source":
    gen_source(sys.argv[2], sys.argv[3])
else:
    raise RuntimeError("invalid argument %s" % sys.argv[1])
