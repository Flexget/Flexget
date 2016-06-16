List Interface
==============

List interface is a unique type of plugin that enables manipulation of its content using flexget normal task operation.
Different phases and interaction with the plugin enable using it as an input, filter or removing entries from it.
It's especially useful for watchlist type list, but not limited to those. Any list that can return entries can be used
as a list interface plugin.

The class of the plugin is based on python's `MutableSet`_ with overrides of its methods where needed.

.. _MutableSet: https://docs.python.org/2/library/collections.html#collections.MutableSet

Usage
-----

As various plugins have different meaning, the specific of the implementation can change. However a few specific override
methods will always be needed, in addition to a few custom ones required by flexget.

Init
~~~~

.. code-block:: python

    class ListInterfaceClass(MutableSet):
        def __init__(self, config):
            self.config.config

The init method should pass the config to a class variable, that will be used by other class methods. Also, any other
global data that is need for the class operation to work should be retrieved. For example, from ``trakt_list``:

.. code-block:: python

    def __init__(self, config):
        self.config = config
        if self.config.get('account') and not self.config.get('username'):
            self.config['username'] = 'me'
        self.session = get_session(self.config.get('account'))
        # Lists may not have modified results if modified then accessed in quick succession.
        self.session.add_domain_limiter(TimedLimiter('trakt.tv', '2 seconds'))
        self._items = None

Note the usage of ``self._items``. In case of an online list, the data should be fetch as little as possible, so a local
cache that can be invalidated should be created. Then a property method that call on that data should be used throughout
the class:

.. code-block:: python

    @property
    def items(self):
        if self._items is None:
            do_stuff()
            self._items = entries
         return self._items

The cache could be invalidated when need by simply resetting the local cache:

.. code-block:: python

    self._items = None

Overridden methods
------------------

Below are code examples of overridden method taken from ``trakt_list`` and ``entry_list``.

``__iter__``
~~~~~~~~~~~~

.. code-block:: python

    def __iter__(self):
        return iter(self.items)

``__len__``
~~~~~~~~~~~

.. code-block:: python

    def __len__(self):
        return len(self.items)


``__discard__``
~~~~~~~~~~~~~~~

.. code-block:: python

    def discard(self, entry, session=None):
        db_entry = self._entry_query(session=session, entry=entry)
        if db_entry:
            log.debug('deleting entry %s', db_entry)
            session.delete(db_entry)

``__ior__``
~~~~~~~~~~~

.. code-block:: python

    def __ior__(self, other):
        # Optimization to only open one session when adding multiple items
        # Make sure lazy lookups are done before opening our session to prevent db locks
        for value in other:
            value.values()
        with Session() as session:
            for value in other:
                self.add(value, session=session)
        return self

``__contains__``
~~~~~~~~~~~~~~~

.. code-block:: python

    @with_session
    def __contains__(self, entry, session=None):
        return self._entry_query(session, entry) is not None

``__add__``
~~~~~~~~~~~

.. code-block:: python

    def add(self, entry):
        self.submit([entry])

``___from_iterable__``
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    def _from_iterable(self, it):
        return set(it)

Custom methods
--------------

These are custom methods that all list type plugin need to implement to work with flexget.

``immutable``
~~~~~~~~~~~~~

Used to specify if some elements of the list plugins are immutable.

.. code-block:: python

    IMMUTABLE_LISTS = ['ratings', 'checkins']

    @property
    def immutable(self):
        if self.config['list'] in IMMUTABLE_LISTS:
            return '%s list is not modifiable' % self.config['list']

``online``
~~~~~~~~~~

Used to determine whether this plugin is an online one and change functionality accordingly in certain situations,
like test mode.

.. code-block:: python

    @property
    def online(self):
        """ Set the online status of the plugin, online plugin should be treated differently in certain situations,
        like test mode"""
        return True


``get``
~~~~~~~

Used to return entry match from internal used. ``list_queue`` plugin calls it in order to create a cached list of entries
and avoid acceptance duplication during filter phase.

.. code-block:: python

    @with_session
    def get(self, entry, session):
        match = self.find_entry(entry=entry, session=session)
        return match.to_entry() if match else None


Plugin format
-------------

After creating the base class, the plugin class itself need to be created.

.. code-block:: python

    class EntryList(object):
        schema = {'type': 'string'}

        @staticmethod
        def get_list(config):
            return DBEntrySet(config)

        def on_task_input(self, task, config):
            return list(DBEntrySet(config))


    @event('plugin.register')
    def register_plugin():
        plugin.register(EntryList, 'entry_list', api_ver=2, groups=['list'])

Note the ``get_list(config)`` method which is mandatory, and the ``on_task_input`` method which enable to use the plugin
as an input plugin.

Also note to register the plugin under the ``list`` group.






