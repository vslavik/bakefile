# MS Visual C++ projects generator script

basename = os.path.splitext(os.path.basename(FILE))[0]
print basename

dsw = """\
Microsoft Developer Studio Workspace File, Format Version 6.00
# WARNING: DO NOT EDIT OR DELETE THIS WORKSPACE FILE!

###############################################################################"""

project = """
Project: "%s"=%s_%s.dsp - Package Owner=<4>

Package=<5>
{{{
}}}

Package=<4>
{{{
%s}}}

###############################################################################
"""

for t in targets:
    deps = ''
    for d in t.__deps.split():
       deps += """\
Begin Project Dependency
Project_Dep_Name %s
End Project Dependency
""" % d
     
    dsw += project % (t.id, basename, t.id, deps)


writer.writeFile(FILE, dsw)
