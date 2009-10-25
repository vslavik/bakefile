
Language reference
==================

The Bakefile language is described in detail in this chapter.


Comments
--------

Bakefile uses C-style comments, in both the single-line and multi-line
variants. Single-line comments look like this:

.. code-block:: none

   // we only generate code for GNU format for now
   toolsets = gnu

Multi-line comments can span several lines:

.. code-block:: none

   /*
      We only generate code for GNU format for now.
      This will change later, when we add Visual C++ support.
    */
   toolsets = gnu

They can also be included in an expression:

.. code-block:: none

   exe hello {
       sources = hello.c /*main() impl*/ lib.c
   }

