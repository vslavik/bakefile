#!/bin/sh

echo "validating...."
#./xml2docbook.py manual.xml >manual.docbook
xmllint --noout --valid manual.docbook

echo "converting to HTML...."
mkdir -p html
(cd html ; xsltproc ../html.xsl ../manual.docbook)

echo "making manpage..."
mkdir -p man
(cd man ; xsltproc ../manpage.xsl ../manual.docbook)
