## ------------------------
## Things you may need to diddle for your local system
## ------------------------

# FIXME: autodetect this
FOP=fop


## ------------------------
## Input files
## ------------------------

BASENAME=manual
MAINDBFILE=$(srcdir)/$(BASENAME).docbook
SUBDBFILES=$(srcdir)/commands.docbook \
		   $(srcdir)/concepts.docbook \
		   $(srcdir)/datafiles.docbook \
		   $(srcdir)/faq.docbook \
		   $(srcdir)/intro.docbook \
		   $(srcdir)/manpage.docbook \
		   $(srcdir)/targets.docbook \
		   $(srcdir)/tutorial.docbook \
    	   $(srcdir)/variables.docbook \
    	   $(srcdir)/functions.docbook
DBFILES=$(MAINDBFILE) $(SUBDBFILES)

FOFILE=$(BASENAME).fo
PDFFILE=$(BASENAME).pdf
FO_SS=$(srcdir)/fo.xsl
HTML_SS=$(srcdir)/html.xsl
MAN_SS=$(srcdir)/manpage.xsl
MANPAGE_MAIN=man/bakefile.1
MANPAGES=man/bakefile.1 man/bakefilize.1


## -------------------------
## Standard Automake targets
## -------------------------

# Notice that we do not build the PDF version by default.  PDF
# generation takes longer than HTML generation, so to keep the code-
# test-debug-rebuild cycle short, we generate only the HTML manual by
# default.  You can explicitly say "make pdf" when you're sure the
# DocBook file's contents are correct.
noinst_DATA=html/index.html

man_MANS = $(MANPAGES)

EXTRA_DIST=$(srcdir)/html/*.css $(srcdir)/*.docbook $(srcdir)/*.xsl \
		   $(srcdir)/html/images/*.png html/*.html \
		   $(MANPAGES)

clean-local:
	rm -rf tags *.fo html man *.log *.out *.pdf


## ---------------------------
## Alternate top-level targets
## ---------------------------

pdf: $(PDFFILE)


## ------------------------
## How to make output files
## ------------------------


html/index.html: $(DBFILES) $(HTML_SS)
	@mkdir -p html
	xmllint --xinclude --postvalid --noent --noout $(MAINDBFILE)
	xsltproc --xinclude -o html/ $(HTML_SS) $(MAINDBFILE)

$(MANPAGE): $(DBFILES) $(MAN_SS)
	@mkdir -p man
	xsltproc --xinclude -o man/ $(MAN_SS) $(MAINDBFILE)

$(PDFFILE): $(DBFILES) $(FO_SS)
	xsltproc --xinclude $(FO_SS) $(MAINDBFILE) > $(FOFILE)
	$(FOP) -q -fo $(FOFILE) $(PDFFILE)

.PHONY: pdf 
