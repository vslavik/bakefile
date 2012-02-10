
Introduction
============

Just Show Me How It Works
-------------------------

If you already have an idea of what Bakefile does, please feel free to skip
directly to the :doc:`tutorial`.


Motivation
----------

Almost any introductory C or C++ book starts with presenting a version of
"Hello, world" program. Some of them also show how to compile the program,
although often enough the reader is advised to refer to the documentation of
the compiler to learn how to do it. And almost none of the books or tutorials
address the issue of how can the program be compiled not in a single
environment and with a single compiler but on several different platforms or,
perhaps, with different compilers on the same platform. And there is a good
reason for avoiding discussing this: surprisingly, 40 years after the
invention of C programming language, there is still no satisfactory solution
to this problem.

Before discussing how Bakefile helps to address it, let's briefly mention the
two usual anti-solutions. The first one of them is to naively separately write
build scripts, make files or projects for each of the environments used. While
there is no problem with this approach as long as a single such environment is
used, accurately propagating changes to one of the files to all the other ones
becomes bothersome even when there are only two of them and, in practice, the
divergences almost inevitably appear. For a cross-platform project, targeting
many different platform, this quickly becomes a serious maintenance burden.
But even for projects used under a single platform, keeping different versions
of the project files can be annoying (a typical example is that of Microsoft
Visual C++ compiler which has changed its project file format with each and
every one of its last 5 releases).

The problems of this naive approach have resulted in creation of a huge number
of cross-platform build tools. This manual is too short to discuss the cons
and pros of each of them, but they all share one fundamental weakness that
makes us classify them all as an anti-solution: the use of such tool replaces
the use of the normal tools used for software development under any given
platform. As anybody who has tried to convince a seasoned Unix programmer to
switch to using Xcode instead of make, a Windows developer to use make instead
of Microsoft Visual Studio or someone used to work with Xcode to live without
it can attest, this can be a bad idea with effects ranging from the drop of
participation in an Open Source project to poisoning the atmosphere in the
office in a company one.


The Bakefile Solution
---------------------

The solution proposed by Bakefile allows to combine the use of native
development tools with the lack of maintenance headaches due to having to
modify the files for each of the tool chains manually. Bakefile is a meta-make
tool which does *not* replace the normal make program or IDE used for building
the project but simply generates the input files for it from a unique
meta-makefile which we call a "bakefile".

It is important to notice that the make and project files created by
bakefile [*]_ are as similar to the files with the same functionality created
by hand as possible, i.e. are easy to understand for anybody familiar with the
underlying tool. These files still should not be modified directly but, in a
pinch, this can be done -- and is as easy to do as with manually crafted
versions.

This need to restrict modifications to the bakefiles themselves and avoid
modifying the files generated from them does require some discipline but this
is the smallest possible price to pay for solving the problem of how to let
developers use their favourite tool chain under all platforms without having
to manually ensure the synchronization between all of them.


.. TODO: Add comparisons with other tools, notably Premake?


.. [*] This process is, inevitably, called "baking".
