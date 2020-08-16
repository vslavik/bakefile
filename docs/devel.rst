
Extending and developing Bakefile
=================================

.. _writing_plugins:

Writing Bakefile plugins
------------------------

As mentioned in :ref:`loading_plugins`, it is possible to use plugins written
in Python to extend Bakefile functionality. The most common types of plugins
are those defining custom tool sets, i.e. new output formats, or custom build
steps, allowing to perform more or less arbitrary actions.

But the simplest possible custom step plugin may actually not do anything at
all, but just define some properties that can be used in bakefiles. For
example, here is a complete example of a plugin:

.. code-block:: py

    from bkl.api import CustomStep, Property
    from bkl.vartypes import StringType

    from datetime import date

    class MyVersion(CustomStep):
        """
        Simple bakefile plugin defining MY_VERSION property.

        The value of the version is just the current date.
        """
        name = "my_version"

        properties_project = [
            Property("MY_VERSION",
                     type=StringType(),
                     default=date.today().isoformat(),
                     inheritable=False,
                     readonly=True),
        ]

This plugin can then be used in the following way:

.. code-block:: bkl

    plugin bkl.plugins.my_version.py;

    program my_program {
        basename = my_program-$(MY_VERSION);
        ...
    }

Of course, a more realistic example would use something other than just the
date of the last Bakefile execution as version. As plugin is just a normal
Python script, there are a lot of possibilities, for example it could extract
the version from the VCS used by the program or read it from some file inside
the source tree.

.. TODO provide an example of implementing generate() in a custom step

.. TODO explain what other plugin types can be used for

Reference
---------

.. toctree::

   api
   internals

