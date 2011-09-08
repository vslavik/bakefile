# Makefile for Sphinx documentation
#

# You can set these variables from the command line.
PYTHONPATH   := $(PYTHONPATH):pygments
SPHINXOPTS   :=
SPHINXBUILD  := PYTHONPATH=$(PYTHONPATH) sphinx-build

# Internal variables.
ALLSPHINXOPTS   = -d .doctrees $(SPHINXOPTS) .

GENERATED_TS = ref/timestamp
GENERATED_DOCS_SOURCES := $(wildcard ../src/bakefile/*.py) \
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
	rm -rf .build .doctrees
	rm -rf html
	rm -rf ref

$(GENERATED_TS): $(GENERATED_DOCS_SOURCES) gen_reference.py
	./gen_reference.py
	@touch $(GENERATED_TS)

html: $(GENERATED_TS)
	mkdir -p html .doctrees
	$(SPHINXBUILD) -b html $(ALLSPHINXOPTS) html
	@echo
	@echo "Build finished. The HTML pages are in ./html."

htmlhelp: $(GENERATED_TS)
	mkdir -p .build/htmlhelp .doctrees
	$(SPHINXBUILD) -b htmlhelp $(ALLSPHINXOPTS) .build/htmlhelp
	@echo
	@echo "Build finished; now you can run HTML Help Workshop with the" \
	      ".hhp project file in .build/htmlhelp."

changes: $(GENERATED_TS)
	mkdir -p .build/changes .doctrees
	$(SPHINXBUILD) -b changes $(ALLSPHINXOPTS) .build/changes
	@echo
	@echo "The overview file is in .build/changes."

linkcheck: $(GENERATED_TS)
	mkdir -p .build/linkcheck .doctrees
	$(SPHINXBUILD) -b linkcheck $(ALLSPHINXOPTS) .build/linkcheck
	@echo
	@echo "Link check complete; look for any errors in the above output " \
	      "or in .build/linkcheck/output.txt."
