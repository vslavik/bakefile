## Process this file with automake to produce Makefile.in

aclocaldir = $(datadir)/aclocal
outputdir = $(pkgdatadir)/output
rulesdir = $(pkgdatadir)/rules
rulesgettextdir = $(rulesdir)/gettext
codedir = $(pkgdatadir)/src
codeoptikdir = $(codedir)/optik

aclocal_DATA = autoconf/bakefile.m4
man_MANS = doc/man/bakefile.1

output_DATA = output/autoconf.empy \
              output/autoconf-macros.empy \
              output/borland.empy

rules_DATA =  rules/autoconf.bkl \
              rules/borland.bkl \
              rules/common.bkl \
              rules/dirs.bkl \
              rules/makefile.bkl \
              rules/makefile_def_borland.bkl \
              rules/makefile_defs_unix.bkl \
              rules/makefile_mingw.bkl
              rules/makefile_macres.bkl
              rules/unixlike.bkl \
              rules/vc5.bkl \
              rules/vc6.bkl \
              rules/version.bkl \
              rules/win32.bkl
rulesgettext_DATA = \
              rules/gettext/common.bkl

code_PYTHON = src/config.py \
              src/bakefile.py \
              src/errors.py \
              src/mk.py \
              src/mk_dump.py \
              src/reader.py \
              src/utils.py \
              src/writer.py \
              src/xmlparser.py \
              src/outmethods.py
codeempy_PYTHON = \
              src/empy/__init__.py \
              src/empy/em.py \
codeoptik_PYTHON = \
              src/optik/__init__.py \
              src/optik/errors.py \
              src/optik/help.py \
              src/optik/option.py \
              src/optik/option_parser.py


EXTRA_DIST = \
    autogen.sh tests doc/images doc bakefile.spec bakefile.iss \
    src/optik/README.txt autoconf output rules \
    src/empy/README src/empy/COPYING

dist-hook:
	(cd $(distdir)/doc ; ./process.sh)
	rm -rf `find $(distdir) -name 'CVS'`

install-data-hook:
	$(mkinstalldirs) $(DESTDIR)$(bindir)
	ln -sf ../share/bakefile/src/bakefile.py $(DESTDIR)$(bindir)/bakefile
	chmod +x $(DESTDIR)/$(codedir)/bakefile.py

ACLOCAL_AMFLAGS = -I admin
