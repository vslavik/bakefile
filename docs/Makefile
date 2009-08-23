# Makefile for Sphinx documentation
#

# You can set these variables from the command line.
SPHINXOPTS    =
SPHINXBUILD   = sphinx-build

# Internal variables.
ALLSPHINXOPTS   = -d .build/doctrees $(SPHINXOPTS) .

GENERATED_TS = ref/timestamp
GENERATED_DOCS_SOURCES = $(wildcard ../src/bakefile/*.py) \
                         $(wildcard ../src/bakefile/plugins/*.py)

.PHONY: all help clean html htmlhelp changes linkcheck

all: html

help:
	@echo "Please use \`make <target>' where <target> is one of"
	@echo "  html      to make standalone HTML files"
	@echo "  htmlhelp  to make HTML files and a HTML help project"
	@echo "  changes   to make an overview over all changed/added/deprecated items"
	@echo "  linkcheck to check all external links for integrity"

clean:
	rm -rf .build/*
	rm -rf ref

$(GENERATED_TS): $(GENERATED_DOCS_SOURCES) gen_reference.py
	./gen_reference.py
	@touch $(GENERATED_TS)

html: $(GENERATED_TS)
	mkdir -p .build/html .build/doctrees
	$(SPHINXBUILD) -b html $(ALLSPHINXOPTS) .build/html
	@echo
	@echo "Build finished. The HTML pages are in .build/html."

htmlhelp: $(GENERATED_TS)
	mkdir -p .build/htmlhelp .build/doctrees
	$(SPHINXBUILD) -b htmlhelp $(ALLSPHINXOPTS) .build/htmlhelp
	@echo
	@echo "Build finished; now you can run HTML Help Workshop with the" \
	      ".hhp project file in .build/htmlhelp."

changes: $(GENERATED_TS)
	mkdir -p .build/changes .build/doctrees
	$(SPHINXBUILD) -b changes $(ALLSPHINXOPTS) .build/changes
	@echo
	@echo "The overview file is in .build/changes."

linkcheck: $(GENERATED_TS)
	mkdir -p .build/linkcheck .build/doctrees
	$(SPHINXBUILD) -b linkcheck $(ALLSPHINXOPTS) .build/linkcheck
	@echo
	@echo "Link check complete; look for any errors in the above output " \
	      "or in .build/linkcheck/output.txt."
