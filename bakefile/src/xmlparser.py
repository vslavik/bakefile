#
#  This file is part of Bakefile (http://bakefile.sourceforge.net)
#
#  Copyright (C) 2003,2004 Vaclav Slavik
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License version 2 as
#  published by the Free Software Foundation.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
#  $Id$
#
#  XML loading via either libxml2 (preferred) or Python's builtin minidom
#  module (which uses expat)
#

# (optional) database with pre-parsed XML files:
cache = None

class Element:
    def __init__(self):
        self.name = None
        self.value = None
        self.props = {}
        self.children = []
        self.filename = None
        self.lineno = None

    def __copy__(self):
        x = Element()
        x.name = self.name
        x.value = self.value
        x.props = self.props
        x.children = self.children
        x.filename = self.filename
        x.lineno = self.lineno
        return x

    def location(self):
        if self.lineno != None:
            return "%s:%i" % (self.filename, self.lineno)
        else:
            return self.filename


class ParsingError(Exception):
    def __init__(self):
        pass

def __libxml2err(ctx, str):
    print str
    raise ParsingError()

def __parseFileLibxml2(filename):
    
    def handleNode(filename, n):
        if n.isBlankNode(): return None
        if n.type != 'element': return None
        
        e = Element()
        e.name = n.name
        e.filename = filename
        e.lineno = n.lineNo()

        prop = n.properties
        while prop != None:
            e.props[prop.name] = prop.content
            prop = prop.next

        c = n.children
        while c != None:
            l = handleNode(filename, c)
            if l != None:
                e.children.append(l)
            c = c.next

        if len(e.children) == 0:
            e.value = n.content.strip()

        return e
   
    try:
        ctxt = libxml2.createFileParserCtxt(filename);
        ctxt.replaceEntities(1)
        ctxt.keepBlanks = 0
        ctxt.validate(0)
        ctxt.lineNumbers(1)
        ctxt.parseDocument()
        doc = ctxt.doc()
        t = handleNode(filename, doc.getRootElement())  
        doc.freeDoc()
        return t
    except libxml2.parserError:
        raise ParsingError()




def __doParseMinidom(func, src):

    def handleNode(filename, n):
        if n.nodeType != n.ELEMENT_NODE: return None
        e = Element()
        e.name = str(n.tagName)
        e.filename = filename

        if n.hasAttributes():
            for p in n.attributes.keys():
                e.props[p] = str(n.getAttribute(p))

        e.value = ''
        for c in n.childNodes:
            if c.nodeType == c.TEXT_NODE:
                e.value += str(c.data)
            else:
                l = handleNode(filename, c)
                if l != None:
                    e.children.append(l)
        e.value = e.value.strip()

        return e
   
    try:
        dom = func(src)
        dom.normalize()
        t = handleNode(src, dom.documentElement)
        dom.unlink()
        return t
    except xml.dom.DOMException, e:
        print e
        raise ParsingError()
    except xml.sax.SAXException, e:
        print e
        raise ParsingError()
    except xml.parsers.expat.ExpatError, e:
        print e
        raise ParsingError()
    except IOError, e:
        print e
        raise ParsingError()

def __parseFileMinidom(filename):
    return __doParseMinidom(xml.dom.minidom.parse, filename)

def __parseStringMinidom(data):
    global xml
    import xml.sax, xml.dom, xml.dom.minidom
    return __doParseMinidom(xml.dom.minidom.parseString, data)

parseString = __parseStringMinidom

def __initParseFileXML():
    # Use libxml2 if available, it gives us better error checking than
    # xml.dom.minidom (DTD validation, line numbers etc.)
    global parseFileXML
    try:
        global libxml2
        import libxml2
        parseFileXML = __parseFileLibxml2
        libxml2.registerErrorHandler(__libxml2err, "-->")
    except(ImportError):
        parseFileXML = __parseFileMinidom
        global xml
        import xml.sax, xml.dom, xml.dom.minidom
        import xml.parsers.expat
        import sys
        sys.stderr.write("Warning: libxml2 missing, will not show line numbers on errors\n")

def __parseFileXMLStub(filename):
    global parseFileXML
    __initParseFileXML()
    return parseFileXML(filename)

parseFileXML = __parseFileXMLStub

def parseFile(filename):
    if cache == None:
        return parseFileXML(filename)
    else:
        if filename in cache:
            return cache[filename]
        else:
            print '*** MISS',filename
            data = parseFileXML(filename)
            cache[filename] = data
            return data
