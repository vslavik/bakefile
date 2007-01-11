#
#  This file is part of Bakefile (http://bakefile.sourceforge.net)
#
#  Copyright (C) 2003-2007 Vaclav Slavik
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy
#  of this software and associated documentation files (the "Software"), to
#  deal in the Software without restriction, including without limitation the
#  rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
#  sell copies of the Software, and to permit persons to whom the Software is
#  furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in
#  all copies or substantial portions of the Software.
#
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
#  FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
#  IN THE SOFTWARE.
#
#  $Id$
#
#  Common part of MS Visual C++ projects generator scripts
#

import fnmatch, re

# ------------------------------------------------------------------------
#   helpers
# ------------------------------------------------------------------------

def sortedKeys(dic):
    l = []
    for c in configs_order:
        if c in dic:
            l.append(c)
    # in VC++ IDE, the last config is the default one, i.e. what you would
    # logically expect to be the first one => reverse the order:
    l.reverse()
    return l

def fixFlagsQuoting(text):
    """Replaces e.g. /DFOO with /D "FOO" and /DFOO=X with /D FOO=X."""
    return re.sub(r'\/([DIid]) ([^ \"=]+)([ $])', r'/\1 "\2"\3',
           re.sub(r'\/([DIid]) ([^ \"=]+)=([^ \"]*)([ $])', r'/\1 \2=\3\4', text))
    

def sortByBasename(files):
    def __sort(x1, x2):
        f1 = x1.split('\\')[-1]
        f2 = x2.split('\\')[-1]
        if f1 == f2: return 0
        elif f1 < f2: return -1
        else: return 1
    files.sort(__sort)


class FilesGroup:
    def __init__(self, name, files):
        self.name = name
        self.files = files

def filterGroups(groups, files):
    """Returns dictionary with files sorted into groups (key: group name).
       Groups are given in 'groups' list of names and 'groupDefs' directory
       as ;-separated wildcards."""
    ret = {}
    used = {}
    for g in groups:
        ret[g.name] = []
        wildcards = g.files.split()
        for w in wildcards:
            for f in files:
                if f in used: continue
                if fnmatch.fnmatch(f, w):
                    used[f] = 1
                    ret[g.name].append(f)
    ret[None] = []
    for f in files:
        if f in used: continue
        ret[None].append(f)
    return ret
        

def organizeFilesIntoGroups(t, defaultGroups, groupClass=FilesGroup):
    """Gets the sources for target @a t organized into groups. Returns
       tuple (sources,groups,files,filesWithCustomBuild) with source files dict
       (key: file, value: configs it's present in), list of groups definitions
       and dict of groups files (key: group name, value: list of files)
       respectively."""

    # (find files from all configs, identify files not in all configs)
    sources = {}
    for c in sortedKeys(t.configs):
        for s in t.configs[c]._sources.split():
            snat = utils.nativePaths(s)
            if snat not in sources:
                sources[snat] = [c]
            else:
                sources[snat].append(c)
    for s in sources:
        if len(sources[s]) == len(t.configs):
            sources[s] = None
    # make copy of the sources specified using <sources>, so that we include
    # them even when they don't match any file group (see below):
    realSources = sources.keys()

    # Add more files that are part of the project but are not built (e.g. 
    # headers, READMEs etc.). They are included unconditionally to save some
    # space.
    for c in sortedKeys(t.configs):
        for s in t.configs[c]._more_files.split():
            snat = utils.nativePaths(s)
            if snat not in sources:
                sources[snat] = None

    # Find files with custom build associated with them and retrieve
    # custom build's code
    filesWithCustomBuild = {}
    for c in sortedKeys(t.configs):
        cbf = t.configs[c]._custom_build_files
        if len(cbf) == 0 or cbf.isspace(): continue
        for f in cbf.split():
            filesWithCustomBuild[f] = {}
    for f in filesWithCustomBuild:
        fname = f.replace('.','_').replace('\\','_').replace('-','_')
        for c in sortedKeys(t.configs):
            filesWithCustomBuild[f][c] = \
                   eval ('t.configs[c]._custom_build_%s' % fname)

    # (sort the files into groups)
    groups = []
    if t._file_groups != '' and not t._file_groups.isspace():
        for gr in t._file_groups.split('\n'):
            grdef = gr.split(':')
            groups.append(groupClass(grdef[0], grdef[1]))
    groups += defaultGroups
    
    files = filterGroups(groups, sources.keys())
    # files that didn't match any group and were specified using <sources>
    # should be added to 'Source Files' group:
    for sf in files[None]:
        if sf in realSources:
            files['Source Files'].append(sf)

    return (sources, groups, files, filesWithCustomBuild)
