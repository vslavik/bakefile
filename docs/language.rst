
Language reference
==================

The Bakefile language is described in detail in this chapter.


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

   if ( $(build_everything) ) {
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

.. [1] Although the syntax imposes few limits, it's not always possible to
       generate makefiles or projects with complicated conditional content even
       though the syntax supports it. In that case, Bakefile will exit with an
       explanatory error message.
