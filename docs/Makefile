# Makefile for Sphinx documentation
#

# You can set these variables from the command line.
SPHINXOPTS   :=
SPHINXBUILD  := sphinx-build

# Internal variables.
ALLSPHINXOPTS   = -d .doctrees $(SPHINXOPTS) .

SPHINX_DOC_FILES := conf.py bkl_lexer.py $(wildcard *.rst)

ALL_DOCS_INPUTS = $(SPHINX_DOC_FILES)

.PHONY: all help clean html htmlhelp changes linkcheck

all: html

help:
	@echo "Please use \`make <target>' where <target> is one of"
	@echo "  html      to make standalone HTML files"
	@echo "  htmlhelp  to make HTML files and a HTML help project"
	@echo "  changes   to make an overview over all changed/added/deprecated items"
	@echo "  linkcheck to check all external links for integrity"

clean:
	rm -rf .build .doctrees
	rm -rf html
	rm -rf ref

html: html/.buildinfo
html/.buildinfo: $(ALL_DOCS_INPUTS)
	mkdir -p html .doctrees
	$(SPHINXBUILD) -b html $(ALLSPHINXOPTS) html
	@echo
	@echo "Build finished. The HTML pages are in ./html."

htmlhelp: $(ALL_DOCS_INPUTS)
	mkdir -p .build/htmlhelp .doctrees
	$(SPHINXBUILD) -b htmlhelp $(ALLSPHINXOPTS) .build/htmlhelp
	@echo
	@echo "Build finished; now you can run HTML Help Workshop with the" \
	      ".hhp project file in .build/htmlhelp."

changes: $(ALL_DOCS_INPUTS)
	mkdir -p .build/changes .doctrees
	$(SPHINXBUILD) -b changes $(ALLSPHINXOPTS) .build/changes
	@echo
	@echo "The overview file is in .build/changes."

linkcheck: $(ALL_DOCS_INPUTS)
	mkdir -p .build/linkcheck .doctrees
	$(SPHINXBUILD) -b linkcheck $(ALLSPHINXOPTS) .build/linkcheck
	@echo
	@echo "Link check complete; look for any errors in the above output " \
	      "or in .build/linkcheck/output.txt."


.PHONY: all help clean html htmlhelp changes linkcheck
