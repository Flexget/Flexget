# pylint: disable=no-self-use
import datetime
import os
import stat
import time

import pendulum
import pytest

from flexget.entry import Entry, EntryUnicodeError
from flexget.utils.template import CoercingDateTime


class TestDisableBuiltins:
    """Quick a hack, test disable functionality by checking if seen filtering (builtin) is working."""

    config = """
        tasks:
          test:
            mock:
              - {title: 'dupe1', url: 'http://localhost/dupe', 'imdb_score': 5}
              - {title: 'dupe2', url: 'http://localhost/dupe', 'imdb_score': 5}
            accept_all: yes
            disable: builtins

          test2:
            mock:
              - {title: 'dupe1', url: 'http://localhost/dupe', 'imdb_score': 5,
                description: 'http://www.imdb.com/title/tt0409459/'}
              - {title: 'dupe2', url: 'http://localhost/dupe', 'imdb_score': 5}
            accept_all: yes
            disable:
              - seen
              - cli_config
    """

    def test_disable_builtins(self, execute_task):
        # Execute the task once, then we'll make sure seen plugin isn't rejecting on future executions
        execute_task('test')
        task = execute_task('test')
        assert task.find_entry('accepted', title='dupe1'), 'disable is not working?'
        assert task.find_entry('accepted', title='dupe2'), 'disable is not working?'
        task = execute_task('test2')
        assert task.find_entry(title='dupe1').accepted, 'disable is not working?'
        assert task.find_entry('accepted', title='dupe2'), 'disable is not working?'


@pytest.mark.online
class TestInputHtml:
    config = """
        tasks:
          test:
            html: http://google.com/
    """

    def test_parsing(self, execute_task):
        task = execute_task('test')
        assert task.entries, 'did not produce entries'


class TestPriority:
    config = """
        tasks:
          test:
            mock:
              - {title: 'Smoke hdtv'}
            accept_all: yes
            set:
              quality: 720p
            quality: 720p
            plugin_priority:
              set: 3
              quality: 2
              accept_all: 1

          test2:
            mock:
              - {title: 'Smoke hdtv'}
            accept_all: yes
            set:
              quality: 720p
            quality: 720p
            plugin_priority:
              set: 3
              quality: 2
              accept_all: 1
    """

    def test_smoke(self, execute_task):
        task = execute_task('test')
        assert task.accepted, (
            'set plugin should have changed quality before quality plugin was run'
        )
        task = execute_task('test2')
        assert task.rejected, 'quality plugin should have rejected Smoke as hdtv'


class TestImmortal:
    config = """
        tasks:
          test:
            mock:
              - {title: 'title1', immortal: yes}
              - {title: 'title2'}
            regexp:
              reject:
                - .*
    """

    def test_immortal(self, execute_task):
        task = execute_task('test')
        assert task.find_entry(title='title1'), 'rejected immortal entry'
        assert not task.find_entry(title='title2'), 'did not reject mortal'


@pytest.mark.online
class TestDownload:
    config = """
        tasks:
          test:
            mock:
              - title: README
                url: https://github.com/Flexget/Flexget/raw/develop/README.MD
                filename: flexget_test_data
            accept_all: true
            download:
              path: __tmp__
              fail_html: no
    """

    def test_download(self, execute_task):
        # A little convoluted, but you have to set the umask in order to have
        # the current value returned to you
        curr_umask = os.umask(0)
        os.umask(curr_umask)
        # executes task and downloads the file
        task = execute_task('test')
        assert task.entries[0]['location'], 'location missing?'
        testfile = task.entries[0]['location']
        assert os.path.exists(testfile), 'download file does not exists'
        testfile_stat = os.stat(testfile)
        assert 0o666 & ~curr_umask == stat.S_IMODE(testfile_stat.st_mode), (
            'download file mode not honoring umask'
        )


class TestEntryUnicodeError:
    def test_encoding(self):
        e = Entry('title', 'url')
        with pytest.raises(EntryUnicodeError):
            e['invalid'] = b'\x8e'


class TestEntryCoercion:
    class MyStr(str):
        __slots__ = ()

    def test_string_coercion(self):
        e = Entry('title', 'url')
        e['test'] = self.MyStr('test')
        assert type(e['test']) is str
        assert e['test'] == 'test'

    def test_datetime_coercion(self):
        # In order for easier use in templates and 'if' plugin, datetimes should be our special instance
        e = Entry('title', 'url')
        e['dt'] = datetime.datetime.now()
        assert isinstance(e['dt'], CoercingDateTime)

    def test_date_coercion(self):
        e = Entry('title', 'url')
        e['date'] = datetime.date(2023, 9, 3)
        assert isinstance(e['date'], pendulum.Date)


class TestFilterRequireField:
    config = """
        tasks:
          test:
            mock:
              - {title: 'Taken[2008]DvDrip[Eng]-FOO', imdb_url: 'http://www.imdb.com/title/tt0936501/'}
              - {title: 'ASDFASDFASDF'}
            require_field: imdb_url
          test2:
            mock:
              - {title: 'Entry.S01E05.720p', series_name: 'Entry'}
              - {title: 'Entry2.is.a.Movie'}
            require_field: series_name
    """

    def test_field_required(self, execute_task):
        task = execute_task('test')
        assert not task.find_entry('rejected', title='Taken[2008]DvDrip[Eng]-FOO'), (
            'Taken should NOT have been rejected'
        )
        assert task.find_entry('rejected', title='ASDFASDFASDF'), (
            'ASDFASDFASDF should have been rejected'
        )

        task = execute_task('test2')
        assert not task.find_entry('rejected', title='Entry.S01E05.720p'), (
            'Entry should NOT have been rejected'
        )
        assert task.find_entry('rejected', title='Entry2.is.a.Movie'), (
            'Entry2 should have been rejected'
        )


class TestHtmlUtils:
    def test_decode_html(self):
        """Utils decode_html."""
        from flexget.utils.tools import decode_html

        assert decode_html('&lt;&#51;') == '<3'
        assert decode_html('&#x2500;') == '\u2500'

    @pytest.mark.skip(reason='FAILS - DISABLED')
    def test_encode_html(self):
        """Utils encode_html (FAILS - DISABLED)."""
        # why this does not encode < ?
        from flexget.utils.tools import encode_html

        print(encode_html('<3'))
        assert encode_html('<3') == '&lt;3'


class TestSetPlugin:
    config = """
        templates:
          global:
            accept_all: yes
        tasks:
          test:
            mock:
              - {title: 'Entry 1'}
            set:
              thefield: TheValue
              otherfield: 3.0
          test_jinja:
            mock:
              - {title: 'Entry 1', series_name: 'Value'}
              - {title: 'Entry 2'}
            set:
              field: 'The {{ series_name|upper }}'
              otherfield: '{% if series_name is not defined %}no series{% endif %}'
              alu: '{{ series_name|re_search(".l.") }}'
          test_non_string:
            mock:
            - title: Entry 1
            set:
              bool: False
              int: 42
          test_lazy:
            mock:
            - title: Entry 1
            set:
              a: "the {{title}}"
          test_lazy_err:
            mock:
            - title: Entry 1
            set:
              title: "{{ao"
              other: "{{eaeou}"
          test_native_types:
            mock:
            - title: Entry 1
            set:
              int_field: "{{3}}"
          test_now:
            disable: [seen]
            mock:
            - title: Entry 1
            set:
              now: "{{now}}"
    """

    def test_set(self, execute_task):
        task = execute_task('test')
        entry = task.find_entry('entries', title='Entry 1')
        assert entry['thefield'] == 'TheValue'
        assert entry['otherfield'] == 3.0

    def test_jinja(self, execute_task):
        task = execute_task('test_jinja')
        entry = task.find_entry('entries', title='Entry 1')
        assert entry['field'] == 'The VALUE'
        assert not entry['otherfield']
        assert entry['alu'] == 'alu'
        entry = task.find_entry('entries', title='Entry 2')
        assert entry['field'] is None, '`field` should be None when jinja rendering fails'
        assert entry['otherfield'] == 'no series'

    def test_non_string(self, execute_task):
        task = execute_task('test_non_string')
        entry = task.find_entry('entries', title='Entry 1')
        assert entry['bool'] is False
        assert entry['int'] == 42

    def test_lazy(self, execute_task):
        task = execute_task('test_lazy')
        entry = task.find_entry('entries', title='Entry 1')
        assert entry.is_lazy('a')
        assert entry['a'] == 'the Entry 1'

    def test_lazy_err(self, execute_task):
        task = execute_task('test_lazy_err')
        entry = task.find_entry('entries', title='Entry 1')
        assert entry['title'] == 'Entry 1', (
            'should fall back to original value when template fails'
        )
        assert entry['other'] is None

    def test_native_types(self, execute_task):
        task = execute_task('test_native_types')
        entry = task.find_entry('entries', title='Entry 1')
        assert isinstance(entry['int_field'], int), (
            'should allow setting values as integers rather than strings'
        )
        assert entry['int_field'] == 3

    def test_now(self, execute_task):
        task = execute_task('test_now')
        entry = task.find_entry('entries', title='Entry 1')
        now = entry['now']
        time.sleep(0.01)
        task = execute_task('test_now')
        entry = task.find_entry('entries', title='Entry 1')
        new_now = entry['now']
        assert now != new_now


class TestCoercingDateTime:
    def test_lt(self):
        now = CoercingDateTime.now()
        later = now.add(hours=1)
        assert now < later
        assert now < later.naive()
        assert now.naive() < later
        assert now.naive() < later.naive()

    def test_eq(self):
        now = CoercingDateTime.now()
        assert now == now.naive()
        assert now.naive() == now

    def test_ne(self):
        now = CoercingDateTime.now()
        assert now == now.naive()
        assert now.naive() == now

    def test_sub(self):
        now = CoercingDateTime.now()
        later = now.add(hours=1)

        assert later - now == pendulum.Duration(hours=1)
        assert later - now.naive() == pendulum.Duration(hours=1)
        assert later.naive() - now == pendulum.Duration(hours=1)
        assert later.naive() - now.naive() == pendulum.Duration(hours=1)

        # Make sure subtracting timedeltas still works
        diff = now - pendulum.Duration(hours=1)
        assert diff == now.subtract(hours=1)
        assert isinstance(diff, CoercingDateTime)
