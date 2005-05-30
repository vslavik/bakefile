## Process this file with automake to produce Makefile.in

aclocaldir = $(datadir)/aclocal
outputdir = $(pkgdatadir)/output
rulesdir = $(pkgdatadir)/rules
rulesgettextdir = $(rulesdir)/gettext
presetsdir = $(pkgdatadir)/presets
codedir = $(pkglibdir)
codeempydir = $(codedir)/empy
codeoptikdir = $(codedir)/optik

bin_SCRIPTS = autoconf/bakefilize

aclocal_DATA = autoconf/bakefile.m4 \
               autoconf/bakefile-lang.m4

man_MANS = doc/man/bakefile.1

output_DATA = output/autoconf.empy \
              output/autoconf-macros.empy \
              output/cbuilderx.py \
              output/borland.empy \
              output/borland-opts.empy \
              output/dmars.empy \
              output/dmars_smake.empy \
              output/dmars-opts.empy \
              output/msvc.empy \
              output/msvc-opts.empy \
              output/msvc6prj.py \
              output/msevc4prj.py \
              output/gnumake.empy \
              output/gnumake-opts.empy \
              output/watcom.empy \
              output/watcom-opts.empy \
              output/xcode2.py \
              output/_hdr_config.empy \
              output/_hdr_makefile.empy

rules_DATA =  rules/FORMATS.bkmanifest \
              rules/autoconf.bkl \
			  rules/cbuilderx.bkl \
              rules/borland.bkl \
              rules/dmars.bkl \
              rules/dmars_smake.bkl \
              rules/dmars_common.bkl \
              rules/common.bkl \
              rules/format_features.bkl \
              rules/datafiles.bkl \
              rules/dirs.bkl \
              rules/makefile.bkl \
              rules/makefile_defs_borland.bkl \
              rules/makefile_defs_dmars.bkl \
              rules/makefile_defs_dmars_common.bkl \
              rules/makefile_defs_dmars_smake.bkl \
              rules/makefile_defs_msvc.bkl \
              rules/makefile_defs_gnu.bkl \
              rules/makefile_defs_mingw.bkl \
              rules/makefile_defs_watcom.bkl \
              rules/makefile_defs_unix.bkl \
              rules/makefile_macres.bkl \
              rules/makefile_os2.bkl \
              rules/makefile_mingw.bkl \
              rules/msvc.bkl \
              rules/msvc_common.bkl \
              rules/msvc_prj_common.bkl \
              rules/msvc6prj.bkl \
              rules/msevc4prj.bkl \
              rules/mingw.bkl \
              rules/gnu.bkl \
              rules/watcom.bkl \
              rules/xcode2.bkl \
              rules/unixlike.bkl \
              rules/version.bkl \
              rules/win32.bkl
rulesgettext_DATA = \
              rules/gettext/common.bkl \
			  rules/gettext/autoconf.bkl
presets_DATA = \
              presets/fake.bkl \
			  presets/simple.bkl

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
              src/outmethods.py \
			  src/bottlenecks.py \
			  src/containers.py \
			  src/portautils.py
codeempy_PYTHON = \
              src/empy/__init__.py \
              src/empy/em.py
codeoptik_PYTHON = \
              src/optik/__init__.py \
              src/optik/errors.py \
              src/optik/help.py \
              src/optik/option.py \
              src/optik/option_parser.py

code_LTLIBRARIES = _bottlenecks.la

_bottlenecks_la_SOURCES = src/bottlenecks.c src/bottlenecks_wrap.c
_bottlenecks_la_LDFLAGS = -module -avoid-version
_bottlenecks_la_CFLAGS = $(PYTHON_CPPFLAGS)

EXTRA_DIST = \
    README THANKS \
    autogen.sh chversion.sh \
	admin/python-devel.m4 \
    tests doc/images doc bakefile.spec bakefile.iss \
    src/optik/README.txt autoconf output rules presets \
    src/empy/README src/empy/COPYING \
	src/bottlenecks.i \
	src/win32scriptwrapper.c \
    makefile.vc

dist-hook:
	(cd $(distdir)/doc ; ./process.sh)
	rm -rf `find $(distdir) -name 'CVS'`

install-data-hook:
	$(mkinstalldirs) $(DESTDIR)$(bindir)
	ln -sf $(codedir)/bakefile.py $(DESTDIR)$(bindir)/bakefile
	ln -sf $(codedir)/bakefile_gen.py $(DESTDIR)$(bindir)/bakefile_gen
	mv $(DESTDIR)$(codedir)/bakefile.py $(DESTDIR)$(codedir)/bakefile.py.x
	mv $(DESTDIR)$(codedir)/bakefile_gen.py $(DESTDIR)$(codedir)/bakefile_gen.py.x
	sed -e "s,#!/usr/bin/env python,#!$(PYTHON),g" $(DESTDIR)$(codedir)/bakefile.py.x >$(DESTDIR)$(codedir)/bakefile.py
	sed -e "s,#!/usr/bin/env python,#!$(PYTHON),g" $(DESTDIR)$(codedir)/bakefile_gen.py.x >$(DESTDIR)$(codedir)/bakefile_gen.py
	rm -f $(DESTDIR)$(codedir)/*.py.x
	chmod +x $(DESTDIR)$(codedir)/bakefile.py
	chmod +x $(DESTDIR)$(codedir)/bakefile_gen.py

ACLOCAL_AMFLAGS = -I admin
