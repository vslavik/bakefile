
Language reference
==================


Statements, blocks, literals etc.
---------------------------------

Statements in Bakefile are separated by newlines, with one statement per line,
similarly to Python.  Unlike in Python, code blocks are marked up in C style,
with ``{`` and ``}``. See an example:

.. code-block:: bkl

   toolsets = gnu vs2010
   exe hello {
       sources = hello.cpp
   }

The problem of expressions that are too long to fit on a single line is handled
in the same way as in Python, with two options:

 1. Escape the newline with ``\``:

    .. code-block:: bkl

       sources = foo.cpp \
                 bar.cpp

 2. Enclose the expression in parenthesis:

    .. code-block:: bkl

       sources = (foo.cpp
                 bar.cpp)



Values, types and literals
--------------------------

Similarly to the ``make`` syntax, quotes around literals are optional --
anything not a keyword or special character or otherwise specially marked is a
literal; specifically, a string literal. Quoting is only needed when the
literal contains whitespace.

Values in Bakefile are typed: properties have types associated with them and
only values that are valid for that type can be assigned to them. The language
isn't *strongly*-typed, though: conversions are performed whenever needed and
possible, variables are untyped by default. Type checking primarily shows up
when validating values assigned to properties.

The basic types are:

 1. *Boolean* properties can be assigned the result of a boolean expression or
    one of the ``true`` or ``false`` literals.

 2. *Strings*. Enough said.

 3. *Lists* are items delimited with whitespace. Lists are typed and the items
    must all be of the same type. In the reference documentation, list types
    are described as "list of string", "list of path" etc.

 4. *Paths* are file or directory paths and are described in more detail in
    the next section.

 5. *IDs* are identifiers of targets.

 6. *Enums* are used for properties where only a few possible values exist; the
    property cannot be set to anything other than one of the listed strings.

 7. ``AnyType`` is the pseudo-type used for untyped variables or expressions
    with undetermined type.



Paths
-----

File paths is a type that deserves more explanation. They are arguably the most
important element in makefiles and project files both and any incorrectness in
them would cause breakage.

All paths in bakefiles must be written using a notation similar to the Unix
one, using ``/`` as the separator, and are always relative. By default, if you
don't say otherwise and write the path as a normal Unix path (e.g.
``src/main.cpp``), it's relative to the *source directory* (or *srcdir* for
short). *Srcdir* is the directory where the input bakefile, in which the path
is written, is. Note that this may be -- and often is -- different from the
location where the generated *output* files are written to.

This is usually the most convenient choice, but it's sometimes not sufficient.
For such situations, Bakefile has the ability to *anchor* paths under a
different root. This is done by adding a prefix of the form of ``@<anchor>/``
in front of the path. The following anchors are recognized:

 1. ``@top_srcdir`` is the toplevel source directory, i.e. *srcdir* of the
    top-most bakefile of the project.

 2. ``@builddir`` is the directory where build files of the current bakefile
    are placed. Note that this is not where the generated makefiles or projects
    go either. It's often a dedicated directory just for the build artifacts
    and typically depends on make-time configuration. Visual Studio, for
    example, puts build files into ``Debug/`` and ``Release/`` subdirectories
    depending on the configuration selected. ``@builddir`` points to these
    directories.

Here are some examples showing common uses for the anchors:

.. code-block:: bkl

   sources = hello.cpp  // relative to srcdir
   sources += @builddir/generated_file.c
   includedirs += @top_srcdir/include



Variables and properties
------------------------

Bakefile allows you to set arbitrary variables on any part of the model.
Additionally, there are *properties*, which are pre-defined variables with a
set meaning. Syntactically, there's no difference between the two. There's
semantical difference in that the properties are usually typed and only values
compatible with their type can be assigned to them. For example, you cannot
assign arbitrary string to a *path* property or overwrite a read-only property.

Variables don't need to be declared; they are defined on first assignment.
Assignment to variables is done in the usual way:

.. code-block:: bkl

   variable = value
   // Lists can be appended to, too:
   sources = foo.cpp
   sources += bar.cpp third.cpp

Because literals aren't quoted, variable references use the ``$()`` make-like
syntax:

.. code-block:: bkl

   platform = windows
   sources += os/$(platform).cpp



Targets
-------

Target definition consists of three things: the *type* of the target (an
executable, a library etc.), it's *ID* (the name, which usually corresponds to
built file's name, but doesn't have to) and detailed specification of its
properties:

.. code-block:: bkl

   type id {
       property = value
       property = value
       ...more content...
   }

(It's a bit more complicated than that, the content may contain conditional
statements too, but that's the overall structure.)



Conditional statements
----------------------

Any part of a bakefile may be enclosed in a conditional ``if`` statement.
The syntax is similar to C/C++'s one:

.. code-block:: bkl

   defines = BUILD
   if ( $(toolset) == gnu ) defines += LINUX

In this example, the ``defines`` list will contain two items, ``[BUILD,
LINUX]`` when generating makefiles for the ``gnu`` toolset and only one item,
``BUILD``, for other toolsets.
The condition doesn't have to be constant, it may reference e.g. options, where
the value isn't known until make-time; Bakefile will correctly translate them into
generated code. [1]_

A long form with curly brackets is accepted as well; unlike the short form,
this one can contain more than one statement:

.. code-block:: bkl

   if ( $(toolset) == gnu ) {
       defines += LINUX
       sources += os/linux.cpp
   }

Conditional statements may be nested, too:

.. code-block:: bkl

   if ( $(build_tests) ) {
       exe test {
           sources = main.cpp
           if ( $(toolset) == gnu ) {
               defines += LINUX
               sources += os/linux.cpp
           }
       }
   }

The expression that specifies the condition uses C-style boolean operators: ``&&``
for *and*, ``||`` for *or*, ``!`` for *not* and ``==`` and ``!=`` for equality
and inequality tests respectively.



Comments
--------

Bakefile uses C-style comments, in both the single-line and multi-line
variants. Single-line comments look like this:

.. code-block:: bkl

   // we only generate code for GNU format for now
   toolsets = gnu

Multi-line comments can span several lines:

.. code-block:: bkl

   /*
      We only generate code for GNU format for now.
      This will change later, when we add Visual C++ support.
    */
   toolsets = gnu

They can also be included in an expression:

.. code-block:: bkl

   exe hello {
       sources = hello.c /*main() impl*/ lib.c
   }



.. [1] Although the syntax imposes few limits, it's not always possible to
       generate makefiles or projects with complicated conditional content even
       though the syntax supports it. In that case, Bakefile will exit with an
       explanatory error message.
