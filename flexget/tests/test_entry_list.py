from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

from flexget.entry import Entry
from flexget.manager import Session
from flexget.plugins.list.entry_list import EntryListList, EntryListEntry


class TestEntryListSearch(object):
    config = """
            tasks:
              entry_list_discover:
                discover:
                  release_estimations: ignore
                  what:
                  - mock:
                    - {title: 'test title'}
                  from:
                  - entry_list_search: 'Test list'

            """

    def test_entry_list_search(self, execute_task):
        entry = Entry()
        entry['title'] = 'test title'
        entry['url'] = ''

        with Session() as session:
            entry_list = EntryListList()
            entry_list.name = 'Test list'
            session.add(entry_list)
            session.commit()

            db_entry = EntryListEntry(entry, entry_list.id)

            entry_list.entries.append(db_entry)

        task = execute_task('entry_list_discover')
        assert len(task.entries) > 0
