# 
# Keeping track of dependencies
#
# $Id$
#

import cPickle

class DepsRecord:
    def __init__(self):
        self.deps = []
        self.outputs = []

deps_db = {}

def addDependency(bakefile, dependency_file):
    """Adds file 'dependency_file' as dependency of bakefile being
       processed."""
    if bakefile == dependency_file: return
    if bakefile not in deps_db:
        deps_db[bakefile] = DepsRecord()
    deps_db[bakefile].deps.append(dependency_file)

def addOutput(bakefile, output_file):
    """Adds file 'output_file' as output created by the bakefile being
       processed."""
    if bakefile not in deps_db:
        deps_db[bakefile] = DepsRecord()
    deps_db[bakefile].deps.append(output_file)
   
def save(filename):
    """Saves dependencies database to a file."""
    f = open(filename,'wb')
    cPickle.dump(deps_db, f, 1)
    f.close()

def load(filename):
    """Loads dependencies database from a file."""
    f = open(filename,'wb')
    global deps_db
    deps_db = cPickle.load(f)
    f.close()

