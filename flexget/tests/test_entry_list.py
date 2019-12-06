from flexget.components.managed_lists.lists.entry_list.db import EntryListEntry, EntryListList
from flexget.entry import Entry
from flexget.manager import Session


class TestEntryListSearch:
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


class TestEntryListQuality:
    config = """
        templates:
          global:
            disable: seen
        tasks:
          verify_quality_1:
            mock:
            - title: foo.bar.720p.hdtv-Flexget
            accept_all: yes
            list_add:
            - entry_list: qual
          verify_quality_2:
            disable: builtins
            entry_list: qual
    """

    def test_quality_in_entry_list(self, execute_task):
        execute_task('verify_quality_1')
        task = execute_task('verify_quality_2')
        entry = task.find_entry(title='foo.bar.720p.hdtv-Flexget')
        assert entry['quality'] == '720p hdtv'
