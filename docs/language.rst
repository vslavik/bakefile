
Language reference
==================


Statements, blocks, literals etc.
---------------------------------

Statements in Bakefile are separated by semicolon (``;``) and code blocks are
marked up in with ``{`` and ``}``, as in C. See an example:

.. code-block:: bkl

   toolsets = gnu vs2010;
   program hello {
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
literal; specifically, a string literal.

Quoting is only needed when the literal contains whitespace or special
characters such as ``=`` or quotes. Quoted strings are enclosed between ``"``
(double quote) or ``'`` (single quote) characters and may contain any
characters except for the quotes. Additionally, backslash (``\``) can be used
inside quoted strings to escape any character. [1]_

The two kinds of quoting differ:

 1. Double-quoted strings are interpolated. That is, variable references using
    ``$(...)`` (see below) are recognized and evaluated. If you want to use
    ``$`` as a literal, you must escape it (``\$``).

 2. Single-quoted strings are literal, ``$`` doesn't have any special meaning
    and is treated as any other character.

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
short). *Srcdir* is the implicitly assumed directory for the input files
specified using relative paths. By default, it is the directory containing the
bakefile itself but it can be changed as described below.  Note that this may
be -- and often is -- different from the location where the generated *output*
files are written to.

This is usually the most convenient choice, but it's sometimes not sufficient.
For such situations, Bakefile has the ability to *anchor* paths under a
different root. This is done by adding a prefix of the form of ``@<anchor>/``
in front of the path. The following anchors are recognized:

 1. ``@srcdir``, as described above.

 2. ``@top_srcdir`` is the top level source directory, i.e. *srcdir* of the
    top-most bakefile of the project. This is only different from @srcdir if
    this bakefile was included from another one as a submodule.

 3. ``@builddir`` is the directory where build files of the current target
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


Changing *srcdir*
^^^^^^^^^^^^^^^^^

As mentioned above, ``@srcdir`` can be changed if its default value is
inconvenient, as, for example, is the case when the bakefile itself is in a
subdirectory of the source tree.

Take this for an example:

.. code-block:: bkl

   // build/bakefiles/foo.bkl
   library foo {
       includedirs += ../../include;
       sources {
           ../../src/foo.cpp
           ../../src/bar.cpp
       }
   }

This can be made much nicer using ``scrdir``:

.. code-block:: bkl

   // build/bakefiles/foo.bkl
   srcdir ../..;

   library foo {
       includedirs += include;
       sources {
           src/foo.cpp
           src/bar.cpp
       }
   }

The ``srcdir`` statement takes one argument, path to the new *srcdir* (relative
to the location of the bakefile). It affects all ``@srcdir``-anchored paths,
including implicitly anchored ones, i.e. those without any explicit anchor, in
the module (but not its submodules). Notably, (default) paths for generated
files are also affected, because these too are relative to ``@srcdir``.

Notice that because it affects the interpretation of all path expressions in
the file, it can only be used before any assignments, target definitions etc.
The only thing that can precede it is ``requires``.


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

Occasionally, it is useful to set variables on other objects, not just in the
current scope. For example, you may want to set per-file compilation flags, add
custom build step for a particular source file or even modify a global
variable. Bakefile uses operator `::` for this purpose, with semantics
reminiscent of C++: any number of scopes delimited by `::` may precede the
variable name, with leading `::` indicating global (i.e. current module) scope.
Here's a simple example:

.. code-block: bkl

   program test {
     sources { foo.cpp bar.cpp }

     // set COMPILING_FOO preprocessor symbol only when compiling foo.cpp:
     foo.cpp::defines += COMPILING_FOO;
   }

   // for demonstration purposes, add an include path to all tests:
   test::includedirs += tests;
   test_another::includedirs += tests;



Referencing variables
^^^^^^^^^^^^^^^^^^^^^

Because literals aren't quoted, variables are referenced using the make-like
``$(<varname>)`` syntax:

.. code-block:: bkl

   platform = windows;
   sources { os/$(platform).cpp }

A shorthand form, where the brackets are omitted, is also allowed when such use
is unambiguous: [2]_

.. code-block:: bkl

   if ( $toolset == gnu ) { ... }

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

   program hello {
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


Templates
---------

It is often useful to share common settings or even code among multiple
targets. This can be handled, to some degree, by setting properties such as
``includedirs`` globally, but more flexibility is often needed.

Bakefile provides a convenient way of doing just that: *templates*. A template
is a named block of code that is applied and evaluated before target's own
body. In a way, it's similar to C++ inheritance: targets correspond to derived
classes and templates would be abstract base classes in this analogy.

Templates can be derived from another template; both targets and templates can
be based on more than one template.  They are applied in the order they are
specified in, with base templates first and derived ones after them. Each
template in the inheritance chain is applied exactly once, i.e. if a target
uses the same template two or more times, its successive appearances are simply
ignored.

Templates may contain any code that is valid inside target definition and may
reference any variables defined in the target.

The syntax is similar to C++ inheritance syntax:

.. code-block:: bkl

   template common_stuff {
       defines += BUILDING;
   }

   template with_logging : common_stuff {
       defines += "LOGGING_ID=\"$(id)\"";
       libs += logging;
   }

   program hello : with_logging {
       sources {
           hello.cpp
       }
   }

Or equivalently:

.. code-block:: bkl

   template common_stuff {
       defines += BUILDING;
   }

   template with_logging {
       defines += "LOGGING_ID=\"$(id)\"";
       libs += logging;
   }

   program hello : common_stuff, with_logging {
       sources {
           hello.cpp
       }
   }


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
generated code. [3]_

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
       program test {
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


.. _configurations:

Build configurations
--------------------

A feature common to many IDEs is support for different build configurations,
i.e. for building the same project using different compilation options.
Bakefile generates the two standard "Debug" and "Release" configurations by
default for the toolsets that usually use them (currently "vs*") and also
supports the use of configurations with the makefile-based toolsets by
allowing to specify ``config=NameOfConfig`` on make command line, e.g.

.. code-block:: sh

    $ make config=Debug
    # ... files are compiled with "-g" option and without optimizations ...

Notice that configuration names shouldn't be case-sensitive as
``config=debug`` is handled in the same way as ``config=Debug`` in make-based
toolsets.

In addition to these two standard configurations, it is also possible to
define your own *custom configurations*, which is especially useful for the
project files which can't be customized as easily as the makefiles at build
time.

Here is a step by step guide to doing this. First, you need to define the new
configuration. This is done by using a configuration declaration in the global
scope, i.e. outside of any target, e.g.:

.. code-block:: bkl

    configuration ExtraDebug : Debug {
    }

The syntax for configuration definition is reminiscent of C++ class definition
and, as could be expected, the identifier after the colon is the name of the
*base configuration*. The new configuration inherits the variables defined in
its base configuration.

Notice that all custom configurations must derive from another existing one,
which can be either a standard "Debug" or "Release" configuration or a
previously defined another custom configuration.

Defining a configuration doesn't do anything on its own, it also needs to be
used by at least some targets. To do it, the custom configuration name must be
listed in an assignment to the special ``configurations`` variable:

.. code-block:: bkl

    configurations = Debug ExtraDebug Release;

This statement can appear either in the global scope, like above, in which
case it affects all the targets, or inside one or more targets, in which case
the specified configuration is only used for these targets. So if you only
wanted to enable extra debugging for "hello" executable you could do

.. code-block:: bkl

    program hello {
        configurations = Debug ExtraDebug Release;
    }

However even if the configuration is present in the generated project files
after doing all this, it is still not very useful as no custom options are
defined for it. To change this, you will usually also want to set some project
options conditionally depending on the configuration being used, e.g.:

.. code-block:: bkl

    program hello {
        if ( $(config) == ExtraDebug ) {
            defines += EXTRA_DEBUG;
        }
    }

``config`` is a special variable automatically set by bakefile to the name of
the current configuration and may be used in conditional expressions as any
other variable.

For simple cases like the above, testing ``config`` explicitly is usually all
you need but in more complex situations it might be preferable to define some
variables inside the configuration definition and then test these variables
instead. Here is a complete example doing the same thing as the above snippets
using this approach:

.. code-block:: bkl

    configuration ExtraDebug : Debug {
        extra_debug = true;
    }

    configurations = Debug ExtraDebug Release;

    program hello {
        if ( $(extra_debug) ) {
            defines += EXTRA_DEBUG;
        }
    }

.. note::

   As mentioned above, it is often unnecessary (although still possible) to
   define configurations for the makefile-based toolsets as it's always
   possible to just write ``make CPPFLAGS=-DEXTRA_DEBUG`` instead of using an
   "ExtraDebug" configuration from the example above with them. If you want to
   avoid such unnnecessary configurations in your makefiles, you could define
   them only conditionally, for example:

   .. code-block:: bkl

       toolsets = gnu vs2010;
       if ( $toolset == vs2010 && $config == ExtraDebug )
           defines += EXTRA_DEBUG;

   would work as before in Visual Studio but would generate a simpler makefile.



Build settings
--------------

Sometimes, configurability provided by *configurations* is not enough and more
flexible settings are required; e.g. configurable paths to 3rdparty libraries,
tools and so on. Bakefile handles this with settings: variable-like constructs
that are, unlike Bakefile variables, preserved in the generated output and can
be modified by the user at make-time.

Settings are part of the object model and as such have a name and additional
properties that affect their behavior. Defining a setting is similar to
defining a target:

   .. code-block:: bkl

       setting JDK_HOME {
           help = "Path to the JDK";
           default = /opt/jdk;
       }

Notice that the setting object has some properties. You will almost always want
to set the two shown in the above example. *help* is used to explain the
setting to the user and *default* provides the default value to use if the user
of the makefile doesn't specify anything else; both are optional. See
:ref:`ref_setting` for the full list.

When you need to reference a setting, use the same syntax as when referencing
variables:

    .. code-block:: bkl

       includedirs += $(JDK_HOME)/include;

In fact, settings also act as variables defined at the highest (project) level.
This means that they can be assigned to as well and some nice tricks are easily
done:

    .. code-block:: bkl

       setting LIBFOO_PATH {
           help = "Path to the Foo library";
           default = /opt/libfoo;
       }

       // On Windows, just use our own copy:
       if ( $toolset == vs2010 )
           LIBFOO_PATH = @top_srcdir/3rdparty/libfoo;

This removes the user setting for toolsets that don't need it. Another handy
use is to import some common code or use a submodule with configurable settings
and just hard-code their values when you don't need the flexibility.

.. note::

   Settings are currently only fully supported by makefiles, they are always
   replaced with their default values in the project files.


Submodules
----------

A bakefile file -- a *module* -- can include other modules as its children.
The ``submodule`` keyword is used for that:

.. code-block:: bkl

   submodule samples/hello/hello.bkl;
   submodule samples/advanced/adv.bkl;

They are useful for organizing larger projects into more manageable chunks,
similarly to how makefiles are used with recursive make. The submodules get
their own makefiles (automatically invoked from the parent module's makefile)
and a separate Visual Studio solution file is created for them by default as
well. Typical uses include putting examples or tests into their own modules.

Submodules may only be included at the top level and cannot be included
conditionally (i.e. inside an ``if`` statement).


Importing other files
---------------------

There's one more way to organize source bakefiles in addition to submodules:
direct import of another file's content. The syntax is similar to submodules
one, using the ``import`` keyword:

.. code-block:: bkl

   // define variables, templates etc:
   import common-defs.bkl;

   program myapp { ... }

Import doesn't change the layout of output files, unlike ``submodule``.
Instead, it directly includes the content of the referenced file at the point
of import. Think of it as a variation on C's ``#include``.

Imports help with organizing large bakefiles into more manageable files. You
could, for example, put commonly used variables or templates, files lists etc.
into their own reusable files.

Notice that there are some important differences to ``#include``:

 1. A file is only imported once *in the current scope*, further imports
    are ignored. Specifically:

    a. Second import of ``foo.bkl`` from the same module is ignored.
    b. Import of ``foo.bkl`` from a submodule is ignored if it was already
       imported into its parent (or any of its ancestors).
    c. If two sibling submodules both import ``foo.bkl`` and none of their
       ancestors does, then the file is imported into *both*. That's because
       their local scopes are independent of each other, so it isn't regarded
       as duplicate import.

 2. An imported file may contain templates or configurations definitions and
    be included repeatedly (in the (1c) case above). This would normally result
    in errors, but Bakefile recognizes imported duplicates as identical and
    handles them gracefully.

The ``import`` keyword can only be included at the top level and cannot be
done conditionally (i.e. inside an ``if`` statement).



Version checking
----------------

If a bakefile depends on features (or even syntax) not available in older
versions, it is possible to declare this dependency using the ``requires``
keyword.

.. code-block:: bkl

   // Feature XYZ was added in Bakefile 1.1:
   requires 1.1;

This statement causes fatal error if Bakefile version is older than the
specified one.



.. _loading_plugins:

Loading plugins
---------------

Standard Bakefile plugins are loaded automatically. But sometimes a custom
plugin needed only for a specific project is needed and such plugins must be
loaded explicitly, using the ``plugin`` keyword:

.. code-block:: bkl

   plugin my_compiler.py;

Its argument is a path to a valid Python file that will be loaded into the
``bkl.plugins`` module. You can also use full name of the module to make it
clear the file is a Bakefile plugin:

.. code-block:: bkl

   plugin bkl.plugins.my_compiler.py;

See the :ref:`writing_plugins` chapter for more information about plugins.



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

   program hello {
       sources { hello.c /*main() impl*/ lib.c }
   }




.. [1] A string literal containing quotes can therefore be written as, say,
       ``"VERSION=\"1.2\""``; backslashes must be escaped as double backslashes
       (``"\\"``).

.. [2] A typical example of *ambiguous* use is in a concatenation. You can't
       write ``$toolset.cpp`` because ``.`` is a valid part of a literal; it
       must be written as ``$(toolset).cpp`` so that it's clear which part is a
       variable name and which is a literal appended to the reference. For
       similar reasons, the shorthand form cannot be used in double-quoted strings.

.. [3] Although the syntax imposes few limits, it's not always possible to
       generate makefiles or projects with complicated conditional content even
       though the syntax supports it. In that case, Bakefile will exit with an
       explanatory error message.
