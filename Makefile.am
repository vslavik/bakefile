## Process this file with automake to produce Makefile.in

aclocaldir = $(datadir)/aclocal
outputdir = $(pkgdatadir)/output
rulesdir = $(pkgdatadir)/rules
rulesmodulesdir = $(rulesdir)/modules
rulesgettextdir = $(rulesmodulesdir)/gettext
presetsdir = $(pkgdatadir)/presets
codedir = $(pkglibdir)
codeempydir = $(codedir)/empy
codepy25modulesdir = $(codedir)/py25modules
schemadir = $(pkgdatadir)/schema

SUBDIRS = doc

bin_SCRIPTS = autoconf/bakefilize

aclocal_DATA = autoconf/bakefile.m4 \
               autoconf/bakefile-lang.m4 \
               autoconf/bakefile-dllar.m4

output_DATA = output/autoconf.empy \
              output/autoconf-macros.empy \
              output/borland.empy \
              output/borland-opts.empy \
              output/dmars.empy \
              output/dmars_smake.empy \
              output/dmars-opts.empy \
              output/msvc.empy \
              output/msvc-opts.empy \
              output/msvc_common.py \
              output/msvc6prj.py \
              output/msevc4prj.py \
			  output/msvs200xprj.py \
              output/gnumake.empy \
              output/gnumake-opts.empy \
              output/watcom.empy \
              output/watcom-opts.empy \
              output/xcode2.py \
              output/symbian.py \
              output/_hdr_config.empy \
              output/_hdr_makefile.empy

rules_DATA =  rules/FORMATS.bkmanifest \
              rules/autoconf.bkl \
              rules/borland.bkl \
              rules/dmars.bkl \
              rules/dmars_smake.bkl \
              rules/dmars_common.bkl \
              rules/common.bkl \
              rules/format_features.bkl \
              rules/dirs.bkl \
              rules/makefile.bkl \
              rules/makefile_defs_borland.bkl \
              rules/makefile_defs_cw.bkl \
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
              rules/msvc_prj_dsp_common.bkl \
              rules/msvc_prj_vcproj_common.bkl \
              rules/msvc6prj.bkl \
              rules/msevc4prj.bkl \
              rules/msvs200xprj.bkl \
              rules/msvs2003prj.bkl \
              rules/msvs2005prj.bkl \
              rules/mingw.bkl \
              rules/gnu.bkl \
              rules/watcom.bkl \
              rules/xcode2.bkl \
              rules/symbian.bkl \
              rules/unixlike.bkl \
              rules/version.bkl \
              rules/win32.bkl
rulesmodules_DATA = \
              rules/modules/datafiles.bkl \
              rules/modules/pkgconfig.bkl
rulesgettext_DATA = \
              rules/modules/gettext/common.bkl \
			  rules/modules/gettext/autoconf.bkl
presets_DATA = \
              presets/fake.bkl \
			  presets/simple.bkl

schema_DATA = \
			  schema/bakefile-gen.xsd \
			  schema/bakefile-manifest.xsd

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
codepy25modules_PYTHON = \
			  src/py25modules/__init__.py \
			  src/py25modules/uuid.py \
			  src/py25modules/subprocess.py

code_LTLIBRARIES = _bottlenecks.la

_bottlenecks_la_SOURCES = src/bottlenecks.c src/bottlenecks_wrap.c
_bottlenecks_la_LDFLAGS = -module -avoid-version
_bottlenecks_la_CFLAGS = $(PYTHON_CPPFLAGS)

EXTRA_DIST = \
    README THANKS \
    bootstrap chversion.sh \
	$(srcdir)/admin/*.m4 \
	bakefile.spec bakefile.iss bakefile.vim bash_completion \
    autoconf output rules presets tests schema \
    src/empy/README src/empy/COPYING \
    src/py25modules/README src/py25modules/LICENSE \
	src/bottlenecks.i \
	src/win32scriptwrapper.c \
	macosx/buildpkg.py macosx/makepkg.sh \
    makefile.vc

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

.PHONY: doc
doc:
	( cd doc ; $(MAKE) )
