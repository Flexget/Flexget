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
                  - entry_list: 'Test list'
              entry_list_with_series:
                max_reruns: 0
                series:
                - foo:
                    begin: s01e01
                discover:
                  release_estimations: ignore
                  what:
                    - next_series_episodes: yes
                  from:
                    - entry_list: series list

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
        assert task.find_entry(title='test title')

    def test_entry_list_with_next_series_episodes(self, execute_task):
        entry = Entry()
        entry['title'] = 'foo.s01e01.720p.hdtv-flexget'
        entry['url'] = ''

        with Session() as session:
            entry_list = EntryListList()
            entry_list.name = 'series list'
            session.add(entry_list)
            session.commit()

            db_entry = EntryListEntry(entry, entry_list.id)
            entry_list.entries.append(db_entry)

        task = execute_task('entry_list_with_series')
        assert task.find_entry('accepted', title='foo.s01e01.720p.hdtv-flexget')
