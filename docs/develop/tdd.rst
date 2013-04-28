TDD in practice
===============

Simple example how to create a plugin with TDD principles.

.. WARNING:: Ironically, this is untested example :)

Create test
-----------

Write new test case called ``tests/test_hello.py``.

.. code::

   from tests import FlexGetBase

   class TestHello(FlexGetBase):

       __yaml__ = """
           tasks:
             test:
               mock:                 # let's use this plugin to create test data
                 - {title: 'foobar'} # we can omit url if we do not care about it, in this case mock will add random url
               hello: yes            # our plugin, no relevant configuration yet ...
       """

       def test_feature(self):
         # run the task
         self.execute_task('test')

Try running the test with nosetests::

  nosetests test_hello

It should complain that the plugin hello does not exists, that's because we
haven't yet created it. Let's do that next.

Create plugin
-------------

Create new file called ``flexget/plugins/output/hello.py``.

Within this file we will add our plugin.

.. code::

   from __future__ import unicode_literals, division, absolute_import
   from flexget.plugin import register_plugin


   class Hello(object):
       pass

   register_plugin(Hello, 'hello', api_ver=2)

After this the unit tests should pass again. Try running them.


Add test
--------

Now our example plugin will be very simple, we just want to add
new field to each entry called ``hello`` with value ``True``.

Let's supplement the testsuite with the test.


.. code::

   from tests import FlexGetBase

   class TestHello(FlexGetBase):

       __yaml__ = """
           tasks:
             test:
               mock:                 # let's use this plugin to create test data
                 - {title: 'foobar'} # we can omit url if we do not care about it, in this case mock will add random url
               hello: yes            # our plugin, no relevant configuration yet ...
       """

       def test_feature(self):
         # run the task
         self.execute_task('test')
         for entry in self.task.entries:
             self.assertEqual(entry.get('hello'), True)

This should fail as we do not currently have such functionality in the plugin.


Add functionality to plugin
---------------------------

Continue by implementing the test case.

.. code::

   from __future__ import unicode_literals, division, absolute_import
   from flexget.plugin import register_plugin


   class Hello(object):
       def on_task_filter(self, task, config):
           for entry in task.entries:
               entry['hello'] = True

   register_plugin(Hello, 'hello', api_ver=2)


Summary
-------

This demonstrates main princible and workflow behind TDD and shows how it can
be achieved with FlexGet.