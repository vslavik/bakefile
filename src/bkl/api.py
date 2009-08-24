#
#  This file is part of Bakefile (http://www.bakefile.org)
#
#  Copyright (C) 2009 Vaclav Slavik
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

# Metaclass used for all extensions in order to implement automatic
# extensions registration. For internal use only.
class _ExtensionMetaclass(type):

    def __init__(cls, name, bases, dct):
        super(_ExtensionMetaclass, cls).__init__(name, bases, dct)

        assert len(bases) == 1, "multiple inheritance not supported"

        # skip base classes, only register implementations:
        if name == "Extension":
            return
        if cls.__base__ is Extension:
            # initialize list of implementations for direct extensions:
            cls.implementations = {}
            return

        if cls.name is None:
            # This must be a helper class derived from a particular extension,
            # but not a fully implemented extension; see e.g. MakefileToolset
            # base class for MingwToolset, BorlandToolset etc.
            return

        # for "normal" implementations of extensions, find the extension
        # type class (we need to handle the case of deriving from an existing
        # extension):
        base = cls.__base__
        while not base.__base__ is Extension:
            base = base.__base__
        if cls.name in base.implementations:
            existing = base.implementations[cls.name]
            raise RuntimeError("conflicting implementations for %s \"%s\": %s.%s and %s.%s" %
                               (base.__name__,
                                cls.name,
                                cls.__module__, cls.__name__,
                                existing.__module__, existing.__name__))
        base.implementations[cls.name] = cls



# instances of all already requested extensions, keyed by (type,name)
_extension_instances = {}


class Extension(object):
    """
    Base class for all Bakefile extensions.

    Extensions are singletons, there's always only one instance of given
    extension at runtime. Use the get() method called on appropriate extension
    type to obtain it. For example:

        exe = TargetType.get("exe")
        # ...do something with it...

    .. attribute:: name

       Use-visible name of the extension. For example, the name for targets
       extensions is what is used in target declarations; likewise for
       property names.

    .. attribute:: implementations

       Dictionary of classes that implement this extension, keyed by their name.
    """

    __metaclass__ = _ExtensionMetaclass

    @classmethod
    def get(cls, name):
        """
        Returns instance of extension with given name and of the extension
        type on which this classmethod was called.

        :param name: name of the extension to read; this corresponds to
            class' "name" attribute
        """
        global _extension_instances
        key = (cls, name)
        if key not in _extension_instances:
            _extension_instances[key] = cls.implementations[name]()
        return _extension_instances[key]

    name = None
    implementations = {}



class Property(object):
    """
    Properties describe variables on targets etc. that are part of the API --
    that is, they have special meaning for the toolset and.
    Unlike free-form variables, properties have a type associated with them
    and any values assigned to them are checked for type correctness. They
    can optionally have a default value, too.

    .. attribute:: name

       Name of the property/variable.

    .. attribute:: default

       Default value of the property or :const:`None`.

    .. attribute:: doc

       Optional documentation for the property.

    Example usage:

    .. code-block:: python

       class FooTarget(bkl.api.TargetType):
           name = "foo"
           properties = [
               Property("defines", default="",
                        doc="compiler predefined symbols for the foo compiler")
           ]
           ...

    """

    def __init__(self, name, default=None, doc=None):
        # FIXME: add type handling
        self.name = name
        self.default = default
        self.__doc__ = doc



class TargetType(Extension):
    """
    Base class for implementation of a new target type.
    """

    #: List of all properties supported on this target type,
    #: as :class:`Property` instances. Note that properties list is
    #: automagically inherited from base classes, if any.
    properties = []



class Toolset(Extension):
    """
    This class encapsulates generating of the project files or makefiles.

    The term "toolset" refers to collection of tools (compiler, linker, make,
    IDE, ...) used to compile programs. For example, "Visual C++ 2008",
    "Visual C++ 2005", "Xcode" or "Borland C++" are toolsets.

    In Bakefile API, this class is responsible for creation of the output. It
    puts all the components (platform-specific commands, make syntax, compiler
    invocation, ...) together and writes out the makefiles or projects.
    """

    #: List of all properties supported on this target type,
    #: as :class:`Property` instances. Note that properties list is
    #: automagically inherited from base classes, if any.
    properties = []


    def generate(self, project):
        """
        Generates all output files for this toolset.

        :param project: model.Project instance with complete description of the
            output. It was already preprocessed to remove content not relevant
            for this toolset (targets or sub-makefiles (FIXME-term)
            built conditionally only for other toolsets, conditionals that are
            always true or false within the toolset and so on).
        """
        raise NotImplementedError
