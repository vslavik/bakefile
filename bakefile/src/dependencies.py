#
# Keeping track of dependencies
#
# $Id$
#

import cPickle, os.path, time

DEPS_FORMAT_VERSION = 3

class DepsRecord:
    def __init__(self):
        self.deps = []
        self.outputs = [] # (filename,method) tuples

deps_db = {}
modtimes_db = {}

def addDependency(bakefile, format, dependency_file):
    """Adds file 'dependency_file' as dependency of bakefile being
       processed."""
    if bakefile == dependency_file: return
    key = (bakefile,format)
    if key not in deps_db:
        deps_db[key] = DepsRecord()
    deps_db[key].deps.append(dependency_file)

def addOutput(bakefile, format, output_file, output_method):
    """Adds file 'output_file' as output created by the bakefile being
       processed."""
    key = (bakefile,format)
    if key not in deps_db:
        deps_db[key] = DepsRecord()
    deps_db[key].outputs.append((output_file, output_method))
    modtimes_db[output_file] = int(time.time())
    
def save(filename):
    """Saves dependencies database to a file."""
    f = open(filename,'wb')
    cPickle.dump(DEPS_FORMAT_VERSION, f, 1)
    cPickle.dump(deps_db, f, 1)
    cPickle.dump(modtimes_db, f, 1)
    f.close()

def load(filename):
    """Loads dependencies database from a file."""
    f = open(filename,'rb')
    global deps_db, modtimes_db
    version = cPickle.load(f)
    if version != DEPS_FORMAT_VERSION:
        raise IOError()
    db = cPickle.load(f)
    if len(deps_db) == 0:
        deps_db = db
    else:
        for k in db:
            deps_db[k] = db[k]
    db = cPickle.load(f)
    if len(modtimes_db) == 0:
        modtimes_db = db
    else:
        for k in db:
            modtimes_db[k] = db[k]
    f.close()


def needsUpdate(bakefile, format):
    """Determines whether the generated makefile in given format from the
       bakefile needs updating."""
    key = (bakefile, format)
    if key not in deps_db:
        # no knowledge of deps or output, must regen:
        return 1

    bakefile_time = os.stat(bakefile).st_mtime

    info = deps_db[key]
    oldest_output = None
    for f, method in info.outputs:
        if not os.path.isfile(f):
            # one of generate files is missing, we must regen:
            return 1
        f_time = os.stat(f).st_mtime
        if f in modtimes_db:
            if modtimes_db[f] > f_time: f_time = modtimes_db[f]
        if oldest_output == None or f_time < oldest_output:
            oldest_output = f_time

    if oldest_output == None:
        return 1

    if oldest_output < bakefile_time:
        return 1

    for f in info.deps:
        if not os.path.isfile(f):
            # one of dependencies is missing, we must regen:
            return 1
        if oldest_output < os.stat(f).st_mtime:
            # one of used bakefiles is newer than generated files:
            return 1

    # this bakefile's output is up-to-date
    return 0
