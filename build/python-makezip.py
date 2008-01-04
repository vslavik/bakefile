#!/usr/bin/env python
#
# Packs Python standard library into zip file python$(ver).zip
#

import os, os.path, shutil, sys
from zipfile import PyZipFile

name = "python%i%i.zip" % (sys.version_info[0], sys.version_info[1])
print "creating %s..." % name

# delete tests, we don't need them:
for root, dirs, files in os.walk("Lib", topdown=False):
    if "test" in dirs:
        shutil.rmtree(os.path.join(root, "test"))

# pack Lib to a zipfile:
zip = PyZipFile(name, mode="w")

for f in os.listdir("Lib"):
    fn = os.path.join("Lib", f)
    if os.path.isdir(fn) or fn.endswith(".py"):
        zip.writepy(fn)
    else:
        print "warning: ignoring file %s" % f

zip.close()
