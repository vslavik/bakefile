
Tutorial
========

Hello, Bakefile
---------------

After complaining about the lack of examples of how "Hello, World" program can
be built in a portable way in the introduction, we'd be amiss to not provide
an example of doing this here. So, assuming the text of the program is in the
file ``hello.c``, here is the corresponding ``hello.bkl`` bakefile to build it:

.. code-block:: bkl

   toolsets = gnu vs2010;
   program hello {
       sources { hello.cpp } // could also have been "hello.c"
   }

To produce something interesting from it we need to run bakefile simply
passing it this file name as argument::

   $ bkl hello.bkl

or maybe::

   C:\> bkl hello.bkl

In the grand tradition of Unix tools, Bakefile doesn't produce any output
after running successfully. If this is too closemouthed for your taste, you
can try adding ``-v`` option which will indicate all the files read and, more
importantly, written by the tool. Using this option or just examining the
directory you ran Bakefile in you can see that it created several new files.

.. Notice that it doesn't matter which platform we run the tool itself under,
.. it will always generate the same output files.

In our case, they will be ``GNUmakefile`` for "gnu" toolset (the one using
standard GNU development tools) or ``hello.sln`` and its supporting files for
"vs2010" toolset (Microsoft Visual Studio 2010) one. These files then can be
used to build the project in the usual way, i.e. by running "make" or opening
the file in the IDE.

Please check that you can run Bakefile and generate a working make or project
file appropriate for your platform ("gnu" for Unix systems including OS X,
"vs2010" for Microsoft Windows ones).


Example Explained
-----------------

Bakefile input language is C-like, with braces and semicolons playing their
usual roles. Additionally, both C and C++ style comments can be used. It
however also borrows some simple and uncontroversial elements [*]_ of make
syntax. Notably, there is no need to quote literal strings and, because of
this, Bakefile variables -- such as ``toolsets`` above -- need to be
explicitly dereferenced using make-file ``$(toolsets)`` expression when
needed.

Knowing this we can see that the first line of the hello bakefile above simply
sets a variable ``toolsets`` to the list of two strings. This variable is
special for Bakefile -- and hence is called "property" rather than a simple
"variable" -- and indicates which make or project files should be generated
when it is ran. It must be present in all bakefiles as no output would be
created without it.

The next block -- ``program hello { ... }`` -- defines an executable target with
the name "hello". All the declarations until the closing bracket affect this
target only. In this simple example the only thing that we have here is the
definition of the sources which should be compiled to build the target. Source
files can be of any type but currently Bakefile only handles C (extension
``.c``) and C++ (extension ``.cpp``, ``.cxx`` or ``.C``) files automatically
and custom compilation rules need to be defined for the other ones. In any
real project there are going to be more than one source file, of course. In
this case they can just be listed all together inside the same block like
this:

.. code-block:: bkl

    sources {
        foo.cpp subdir/bar.cpp
        // Not necessarily on the same line
        baz.cpp
    }

or they can be separated in several blocks:

.. code-block:: bkl

    sources { foo.cpp }
    sources { subdir/bar.cpp }
    sources { baz.cpp }

The two fragments have exactly the same meaning.


Customizing Your Project
------------------------

Compilation And Linking Options
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A realistic project needs to specify not only the list of files to compile but
also the options to use for compiling them. The most common options needed for
C/C++ programs are the include paths allowing to find the header file used and
the preprocessor definitions and Bakefile provides convenient way to set both
of them by assigning to ``defines`` and ``includedirs`` properties inside a
target:

.. code-block:: bkl

    program hello {
        defines = FOO "DEBUG=1";    // Quotes are needed if value is given
        includedirs = ../include;
        ...
    }

These properties can be set more than once but each subsequent assignment
overrides the previous value which is not particular useful. It can be more
helpful to append another value to the property instead, for example:

.. code-block:: bkl

    program hello {
        defines = FOO;
        ...
        defines += BAR;
        ...
        defines += "VERSION=17";
        defines += "VERSION_STR=\"v17\"";
    }

will define "FOO" and "BAR" symbols (without value) as well as "VERSION" with
the value of 17 and "VERSION_STR" with the value as a C string during
compilation. This is still not very exciting as all these values could have
been set at once, but the possibility of conditional assignment is more
interesting:

.. code-block:: bkl

    program hello {
        if ( $(toolset) == gnu )
            defines += LINUX;
        if ( $(toolset) == vs2010 )
            defines += MSW;
    }

would define ``LINUX`` only for makefile-based build and ``MSW`` for the
project files.

While ``defines`` and ``includedirs`` are usually enough to cover 90% of your
needs, sometimes some other compiler options may need to be specified and the
``compiler-options`` property can be used for this: you can simply any options
you want to be passed to C or C++ compiler into it. If you need to be more
precise and only use some options with a particular compiler in a project
using more than one of them, you can also use ``c-compiler-options`` or
``cxx-compiler-options``.

One aspect of using these properties is that different compilers use different
format for their options, so it's usually impossible to use the same value for
all of them. Moreover, sometimes you may actually need to use custom options
for a single toolset only. This can be done by explicitly testing for the
toolset being used. For example, to use C++ 11 features with GNU compiler you
could do

.. code-block:: bkl

    if ( $(toolset) == gnu )
        cxx-compiler-options = "-std=c++11"


Similarly, any non trivial project usually links with some external libraries.
To specify these libraries, you need to assign to the ``libs`` property and
also may need to set ``libdirs`` if these libraries are not present in the
standard search path:

.. code-block:: bkl

    program hello {
        libdirs = ../3rdparty/somelib/lib;
        libs = somelib;
    }

Notice that you only need to do the latter if the libraries are not built as
part of the same project, otherwise you should simply list them as
dependencies as shown in the next section.

And if you need to use any other linker option you can specify it using
``link-options`` property. As with compiler options, you would normally test
for the toolkit before doing it as linker options are toolset-specific.


Multiple Modules
^^^^^^^^^^^^^^^^

Larger projects typically consist in more than just a single executable but of
several of them and some libraries. The same bakefile can contain definitions
of all of them:

.. code-block:: bkl

    library network {
        sources { ... }
    }

    library gui {
        sources { ... }
    }

    program main {
        deps = network gui;
        ...
    }

In this case, the libraries will be built before the main executable and will
be linked with it. Bakefile is smart about linking and if a library has
dependencies of its own, these will be linked in as well.

Alternatively, you can define each library or executable in its own bakefile.
This is especially convenient if each of them is built in a separate
directory. In this case you can use ``submodule`` keyword to include the
sub-bakefiles.



Assorted Other Options
^^^^^^^^^^^^^^^^^^^^^^

Under Windows, console and GUI programs are compiled differently. By default,
Bakefile builds console executables. You can change this by setting the
``win32-subsystem`` property to ``windows``.

Another Windows-specific peculiarity is that standard C run-time library
headers as well as Platform SDK headers are compiled differently depending on
whether ``_UNICODE`` and ``UNICODE`` macros, respectively, are defined or not.
By default, Bakefile does define these macros but you can set ``win32-unicode``
target property to ``false`` to prevent it from doing it.

Finally, Windows projects generated by default only contain configurations for
Win32 platform. To generate 64 bit configurations as well, you need to
explicitly request them by defining the architectures to build for:

.. code-block:: bkl

   archs = x86 x86_64;

The name of 64 bit architecture is ``x86_64`` and not ``x64`` which is usually
used under Windows because the architectures are also used under other
platforms, notably OS X where universal binaries containing both 32 bit and 64
bit binaries would be built with the above value of ``archs``.

.. [*] So no meaningful tabulations or backslashes for line continuation.


Advanced Stuff
--------------

Generated Source Files
^^^^^^^^^^^^^^^^^^^^^^

Bakefile supports custom compilation steps; this can be used both for files
generated with some script and for compilation of unsupported file types.

Compiling a custom file is as simple as setting the ``compile-commands``
property on it to the command (or several commands) to compile the file,
``outputs`` property with the list of created files and optionally filling in
additional dependencies:

.. code-block:: bkl

   toolsets = gnu vs2010;
   program hello {
       sources { hello.cpp mygen.cpp mygen.desc }

       mygen.desc::compile-commands = "tools/generator.py -o %(out) %(in)";
       mygen.desc::outputs = mygen.cpp;
       // add dependency on the generator script:
       mygen.desc::dependencies = tools/generator.py;
   }

Notice that the generated files listed in ``outputs`` must be included in
``sources`` or ``headers`` section as well.

Additionally, any number of other dependency files can be added to the
``dependencies`` list.  The command uses two placeholders, ``%(in)`` and
``%(out)``, that are replaced with the name of the source file (``mygen.desc``
in our example) and ``outputs`` respectively; both placeholders are optional.
If there are multiple output files, ``%(out0)``, ``%(out1)``, ... placeholders
can be used to access individual items in the list.

Perhaps a better would be to demonstrate how to use this to generate a grammar
parser with Bison:

.. code-block:: bkl

   sources {
       main.cpp
       parser.ypp              // Bison grammar file
       parser.cpp parser.hpp   // generated C++ parser
   }

   parser.ypp::compile-commands = "bison -o %(out0) %(in)"
   parser.ypp::outputs = parser.cpp parser.hpp;
