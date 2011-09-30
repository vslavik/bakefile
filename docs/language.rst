
Language reference
==================


Statements, blocks, literals etc.
---------------------------------

Statements in Bakefile are separated by semicolon (``;``) and code blocks are
marked up in with ``{`` and ``}``, as in C. See an example:

.. code-block:: bkl

   toolsets = gnu vs2010;
   exe hello {
       sources { hello.cpp }
   }

In particular, expressions may span multiple lines without the need to escape newlines or enclose the
expression in parenthesis:

.. code-block:: bkl

   os_files = foo.cpp
              bar.cpp
              ;



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

 1. ``@top_srcdir`` is the top level source directory, i.e. *srcdir* of the
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

   sources {
       hello.cpp;  // relative to srcdir
       @builddir/generated_file.c;
   }
   includedirs += @top_srcdir/include;



Variables and properties
------------------------

Bakefile allows you to set arbitrary variables on any part of the model.
Additionally, there are *properties*, which are pre-defined variables with a
set meaning. Syntactically, there's no difference between the two. There's
semantical difference in that the properties are usually typed and only values
compatible with their type can be assigned to them. For example, you cannot
assign arbitrary string to a *path* property or overwrite a read-only property.


Setting variables
^^^^^^^^^^^^^^^^^

Variables don't need to be declared; they are defined on first assignment.
Assignment to variables is done in the usual way:

.. code-block:: bkl

   variable = value;
   // Lists can be appended to, too:
   main_sources = foo.cpp;
   main_sources += bar.cpp third.cpp;


Referencing variables
^^^^^^^^^^^^^^^^^^^^^

Because literals aren't quoted, variables are referenced using the make-like
``$(<varname>)`` syntax:

.. code-block:: bkl

   platform = windows;
   sources { os/$(platform).cpp }

Note that the substitution isn't done immediately. Instead, the reference is
included in the object model of the bakefiles and is dereferenced at a later
stage, when generating makefile and project files. Sometimes, they are kept in
the generated files too.

This has two practical consequences:

 1. It is possible to reference variables that are defined later in the
    bakefile without getting errors.

 2. Definitions cannot be recursive, a variable must not reference itself. You
    cannot write this:

    .. code-block:: bkl

       defines = $(defines) SOME_MORE

    Use operator ``+=`` instead:

    .. code-block:: bkl

       defines += SOME_MORE


Targets
-------

Target definition consists of three things: the *type* of the target (an
executable, a library etc.), its *ID* (the name, which usually corresponds to
built file's name, but doesn't have to) and detailed specification of its
properties:

.. code-block:: bkl

   type id {
       property = value;
       property = value;
       ...sources specification...
       ...more content...
   }

(It's a bit more complicated than that, the content may contain conditional
statements too, but that's the overall structure.)


Sources files
^^^^^^^^^^^^^

Source files are added to the target using the ``sources`` keyword, followed by
the list of source files inside curly brackets. Note the sources list may
contain any valid expression; in particular, references to variables are
permitted.

It's possible to have multiple ``sources`` statements in the same target.
Another use of ``sources`` appends the files to the list of sources, it doesn't
overwrite it; the effect is the same as that of operator ``+=``.

See an example:

.. code-block:: bkl

   exe hello {
       sources {
           hello.cpp
           utils.cpp
       }

       // add some more sources later:
       sources { $(EXTRA_SOURCES) }
   }


Headers
^^^^^^^

Syntax for headers specification is identical to the one used for source files,
except that the ``headers`` keyword is used instead. The difference between
sources and headers is that the latter may be used outside of the target (e.g.
a library installs headers that are then used by users of the library).



Conditional statements
----------------------

Any part of a bakefile may be enclosed in a conditional ``if`` statement.
The syntax is similar to C/C++'s one:

.. code-block:: bkl

   defines = BUILD;
   if ( $(toolset) == gnu )
       defines += LINUX;

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
       defines += LINUX;
       sources { os/linux.cpp }
   }

Conditional statements may be nested, too:

.. code-block:: bkl

   if ( $(build_tests) ) {
       exe test {
           sources { main.cpp }
           if ( $(toolset) == gnu ) {
               defines += LINUX;
               sources { os/linux.cpp }
           }
       }
   }

The expression that specifies the condition uses C-style boolean operators: ``&&``
for *and*, ``||`` for *or*, ``!`` for *not* and ``==`` and ``!=`` for equality
and inequality tests respectively.



Submodules
----------

A bakefile file -- a *module* can include other modules as its children. This
maps to invoking makefiles in subdirectories when generating makefile-based
output. The ``submodule`` keyword is used for that:

.. code-block:: bkl

   submodule samples/hello/hello.bkl;
   submodule samples/advanced/adv.bkl;

Submodules may only be included at the top level and cannot be included
conditionally (i.e. inside an ``if`` statement).



Comments
--------

Bakefile uses C-style comments, in both the single-line and multi-line
variants. Single-line comments look like this:

.. code-block:: bkl

   // we only generate code for GNU format for now
   toolsets = gnu;

Multi-line comments can span several lines:

.. code-block:: bkl

   /*
      We only generate code for GNU format for now.
      This will change later, when we add Visual C++ support.
    */
   toolsets = gnu;

They can also be included in an expression:

.. code-block:: bkl

   exe hello {
       sources { hello.c /*main() impl*/ lib.c }
   }



.. [1] Although the syntax imposes few limits, it's not always possible to
       generate makefiles or projects with complicated conditional content even
       though the syntax supports it. In that case, Bakefile will exit with an
       explanatory error message.
