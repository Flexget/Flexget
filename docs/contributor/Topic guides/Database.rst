Database
========

FlexGet uses `SQLAlchemy`_ for database access. There are however some custom
additions that developers should be aware of.

.. _SQLAlchemy: http://www.sqlalchemy.org/

Migrations
----------

The plugin system tries to make each plugin as much separated as possible. When
the need for schema migrations became too overwhelming the team evaluated few
possibilities but none of them were able to version each plugin separately. Even
the latest official tool from SQLAlchemy authors does not seem to make it easily
possible.

Because this special requirement we had to make custom implementation for migrations.


Migrate Base
~~~~~~~~~~~~

The plugin needs only to use custom ``Base`` from :func:`flexget.db_schema.versioned_base`.

::

   SCHEMA_VER = 0
   Base = schema.versioned_base('plugin_name_here', SCHEMA_VER)

This will automatically track all the declarative models plugin uses. When there
are changes in the plugin database, increment the number and add migration code.
This is done with decorated function in the following manner.

::

   @schema.upgrade('series')
   def upgrade(ver, session):
       if ver==1:
           # upgrade actions
           ver = 2
       return ver

.. warning::

   The upgrade function can NOT use any declarative models. That will break sooner
   or later when models are evolving.

There are several helper functions available in :mod:`flexget.utils.sqlalchemy_utils` that
allow querying database reflectively. Use SQLAlchemy's core expression to make alterations
to the table structure.


Database cleanups
-----------------

If the plugin accumulates data into database that should be cleaned at some point
`manager.db_cleanup` event should be used. This will be automatically called every
7 days in non intrusive way.

::

   @event('manager.db_cleanup')
   def db_cleanup(session):
       # cleanup actions here
