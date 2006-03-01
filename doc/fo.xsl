<?xml version="1.0" encoding="utf-8"?>

<!-- XSL stylesheet containing additions to the standard DocBook
     XSL-FO stylesheet.
-->

<xsl:stylesheet
		xmlns:xsl="http://www.w3.org/1999/XSL/Transform" 
		xmlns:fo="http://www.w3.org/1999/XSL/Format"
		version="1.0">
	
	<!-- Import the standard DocBook stylesheet that this one is based on.
	     We use a web URL, but the local XML catalog should resolve this to
			 the local copy of the stylesheet, if it exists. -->
	<xsl:import href="http://docbook.sourceforge.net/release/xsl/current/fo/docbook.xsl"/>
</xsl:stylesheet>
