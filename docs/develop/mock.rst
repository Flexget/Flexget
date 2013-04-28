Mock data
=========

If you're not really hard core into `TDD`_ you still need some practical
way to test how your plugin or changes behave. From here you can find
some ways to achieve that.

.. _TDD: http://en.wikipedia.org/wiki/Test_driven_development

Mock input
----------

Using special input plugin called ``mock`` to produce almost any kind of
entries in a task. This is probably one of the best ways to test things
outside TDD.

Example:

.. highlights:: yaml

   tasks:
     my-test:
       mock:
         - {title: 'title of test', description: 'foobar'}
       my_custom_plugin:
         do_stuff: yes

This will generate one entry in the task, notice that entry has two mandatory
fields ``title`` and ``url``. If ``url`` is not defined the mock plugin will
generate random url for localhost. The ``description`` filed is just arbitary
field that we define in here. We can define any kind of basic text, number, list
or dictionary fields in here.


Inject
------

The argument ``--inject`` is very useful during development, assuming previous
example configuration you could try with some other title simply running following.

Example::

  flexget --inject "another test title"

The ``--inject`` will disable any other inputs in the task. It is possible to set
arbitrary fields trough inject much like with mock. See `full documentation here`_.

.. _full documentation here: http://flexget.com/wiki/Plugins/--inject

Commandline values
------------------

The plugin `cli config`_ may be useful if you need to try bunch of different values
in the configuration file. It allows placing variables in the configuration file.

Example:

.. highlights:: yaml

   task:
     my-test:
       mock:
         - {title: foobar}
       regexp:
         accept:
           - $regexp


Run with command::

  flexget --cli-config "regexp=foobar"

.. _cli config: http://flexget.com/wiki/Plugins/--cli-config