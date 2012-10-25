#!/usr/bin/env python

import sys

if len(sys.argv) != 4:
    raise RuntimeError("invalid arguments")

with file(sys.argv[2], "wt") as f:
    if sys.argv[1] == "--header":
        f.write("extern const char *get_msg();\n")
    elif sys.argv[1] == "--source":
        f.write("const char *get_msg() { return \"Hello!\"; }\n")
    else:
        raise RuntimeError("invalid argument %s" % sys.argv[1])
