#!/bin/sh

echo "validating...."
#./xml2docbook.py manual.xml >manual.docbook
xmllint --noout --postvalid --xinclude manual.docbook

echo "converting to HTML...."
mkdir -p html
(cd html ; xsltproc --xinclude ../html.xsl ../manual.docbook)

echo "making manpage..."
mkdir -p man
(cd man ; xsltproc --xinclude ../manpage.xsl ../manual.docbook)
