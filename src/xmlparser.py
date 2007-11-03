#
#  This file is part of Bakefile (http://www.bakefile.org)
#
#  Copyright (C) 2003-2007 Vaclav Slavik
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy
#  of this software and associated documentation files (the "Software"), to
#  deal in the Software without restriction, including without limitation the
#  rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
#  sell copies of the Software, and to permit persons to whom the Software is
#  furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in
#  all copies or substantial portions of the Software.
#
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
#  FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
#  IN THE SOFTWARE.
#
#  $Id$
#
#  XML loading via either libxml2 (preferred) or Python's builtin minidom
#  module (which uses expat)
#

import sys

# namespaces used by Bakefile:
NS_FORMATS_MANIFEST = "http://www.bakefile.org/schema/bakefile-formats"
NS_BAKEFILE_GEN     = "http://www.bakefile.org/schema/bakefile-gen"

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
            return "%s (%s)" % (self.filename,
                                "line unknown, install libxml2 to show it")


class ParsingError(Exception):
    def __init__(self):
        pass

def __libxml2err(ctx, str):
    print str
    raise ParsingError()

def __libxml2schemaErr(msg, filename):
    sys.stderr.write("error: file %s doesn't conform to schema: %s\n" % (filename, msg))

def __validateSchema(doc, namespace):
    if namespace == None:
        return
    root = doc.getRootElement()
    ns = root.ns()
    if ns == None:
        sys.stderr.write("%s:%i: warning: missing namespace declaration, should be \"%s\"\n" % (doc.name, root.lineNo(), namespace))
        return # we can't validate it without namespace
    elif ns.content != namespace:
        sys.stderr.write("%s:%i: error: document has wrong namespace \"%s\", should be \"%s\"\n" % (doc.name, root.lineNo(), ns.content, namespace))
        raise ParsingError()

    import os.path
    from config import datadir

    if namespace == NS_FORMATS_MANIFEST:
        schemaFile = os.path.join(datadir, 'schema', 'bakefile-manifest.xsd')
    elif namespace == NS_BAKEFILE_GEN:
        schemaFile = os.path.join(datadir, 'schema', 'bakefile-gen.xsd')
    else:
        return

    if not os.path.isfile(schemaFile):
        sys.stderr.write("warning: can't find schema definition %s, skipping validation\n" % schemaFile)
        return

    ctxt = libxml2.schemaNewParserCtxt(schemaFile)
    schema = ctxt.schemaParse()
    valid = schema.schemaNewValidCtxt()
    valid.setValidityErrorHandler(__libxml2schemaErr, __libxml2schemaErr, doc.name)
    if doc.schemaValidateDoc(valid) != 0:
        raise ParsingError()



def __parseFileLibxml2(filename, namespace):
    
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
        __validateSchema(doc, namespace)
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

def __parseFileMinidom(filename, namespace):
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
        import sys, xml.sax, xml.dom, xml.dom.minidom, xml.parsers.expat

def __parseFileXMLStub(filename, namespace):
    global parseFileXML
    __initParseFileXML()
    return parseFileXML(filename, namespace)

parseFileXML = __parseFileXMLStub

def parseFile(filename, namespace=None):
    if cache == None:
        return parseFileXML(filename, namespace)
    else:
        if filename in cache:
            return cache[filename]
        else:
            data = parseFileXML(filename, namespace)
            cache[filename] = data
            return data
