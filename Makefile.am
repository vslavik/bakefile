## Process this file with automake to produce Makefile.in

aclocaldir = $(datadir)/aclocal
outputdir = $(pkgdatadir)/output
rulesdir = $(pkgdatadir)/rules
rulesgettextdir = $(rulesdir)/gettext
codedir = $(pkgdatadir)/src
codeempydir = $(codedir)/empy
codeoptikdir = $(codedir)/optik

aclocal_DATA = autoconf/bakefile.m4
man_MANS = doc/man/bakefile.1

output_DATA = output/autoconf.empy \
              output/autoconf-macros.empy \
              output/borland.empy \
              output/borland-opts.empy \
              output/msvc.empy \
              output/msvc-opts.empy \
              output/msvc6prj.py \
              output/mingw.empy \
              output/mingw-opts.empy \
              output/watcom.empy \
              output/watcom-opts.empy \
              output/_hdr_makefile.empy

rules_DATA =  rules/FORMATS.bkmanifest \
              rules/autoconf.bkl \
              rules/borland.bkl \
              rules/common.bkl \
              rules/format_features.bkl \
              rules/datafiles.bkl \
              rules/dirs.bkl \
              rules/makefile.bkl \
              rules/makefile_defs_borland.bkl \
              rules/makefile_defs_msvc.bkl \
              rules/makefile_defs_mingw.bkl \
              rules/makefile_defs_watcom.bkl \
              rules/makefile_defs_unix.bkl \
              rules/makefile_macres.bkl \
              rules/makefile_mingw.bkl \
              rules/msvc.bkl \
              rules/msvc6prj.bkl \
              rules/msvc_common.bkl \
              rules/mingw.bkl \
              rules/watcom.bkl \
              rules/unixlike.bkl \
              rules/version.bkl \
              rules/win32.bkl
rulesgettext_DATA = \
              rules/gettext/common.bkl \
			  rules/gettext/autoconf.bkl

code_PYTHON = src/config.py \
              src/bakefile.py \
              src/bakefile_gen.py \
              src/errors.py \
              src/finalize.py \
              src/flatten.py \
			  src/formats.py \
              src/mk.py \
              src/mk_dump.py \
              src/reader.py \
              src/utils.py \
              src/writer.py \
              src/xmlparser.py \
			  src/dependencies.py \
              src/outmethods.py
codeempy_PYTHON = \
              src/empy/__init__.py \
              src/empy/em.py
codeoptik_PYTHON = \
              src/optik/__init__.py \
              src/optik/errors.py \
              src/optik/help.py \
              src/optik/option.py \
              src/optik/option_parser.py


EXTRA_DIST = \
    README THANKS \
    autogen.sh chversion.sh \
    tests doc/images doc bakefile.spec bakefile.iss \
    src/optik/README.txt autoconf output rules \
    src/empy/README src/empy/COPYING \
	src/win32scriptwrapper.c \
	src/bakefile.exe \
	src/bakefile_gen.exe

dist-hook:
	(cd $(distdir)/doc ; ./process.sh)
	rm -rf `find $(distdir) -name 'CVS'`

install-data-hook:
	$(mkinstalldirs) $(DESTDIR)$(bindir)
	ln -sf ../share/bakefile/src/bakefile.py $(DESTDIR)$(bindir)/bakefile
	chmod +x $(DESTDIR)/$(codedir)/bakefile.py
	ln -sf ../share/bakefile/src/bakefile_gen.py $(DESTDIR)$(bindir)/bakefile_gen
	chmod +x $(DESTDIR)/$(codedir)/bakefile_gen.py

ACLOCAL_AMFLAGS = -I admin
