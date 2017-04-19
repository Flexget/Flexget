# pylint: disable=no-self-use

from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from future.utils import text_type

import os
import stat

import pytest

from flexget.entry import EntryUnicodeError, Entry


class TestDisableBuiltins(object):
    """
        Quick a hack, test disable functionality by checking if seen filtering (builtin) is working
    """

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
        assert task.find_entry('accepted', title='dupe1') and task.find_entry('accepted', title='dupe2'), \
            'disable is not working?'
        task = execute_task('test2')
        assert task.find_entry(title='dupe1').accepted and task.find_entry('accepted', title='dupe2'), \
            'disable is not working?'


@pytest.mark.online
class TestInputHtml(object):
    config = """
        tasks:
          test:
            html: http://download.flexget.com/
    """

    def test_parsing(self, execute_task):
        task = execute_task('test')
        assert task.entries, 'did not produce entries'


class TestPriority(object):
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
        assert task.accepted, 'set plugin should have changed quality before quality plugin was run'
        task = execute_task('test2')
        assert task.rejected, 'quality plugin should have rejected Smoke as hdtv'


class TestImmortal(object):
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
class TestDownload(object):
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

    def test_download(self, execute_task, tmpdir):
        # NOTE: what the hell is .obj and where it comes from?
        # Re: seems to come from python mimetype detection in download plugin ...
        # Re Re: Implemented in such way that extension does not matter?
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
        modes_equal = 0o666 & ~curr_umask == stat.S_IMODE(testfile_stat.st_mode)
        assert modes_equal, 'download file mode not honoring umask'


class TestEntryUnicodeError(object):
    def test_encoding(self):
        e = Entry('title', 'url')
        with pytest.raises(EntryUnicodeError):
            e['invalid'] = b'\x8e'


class TestEntryStringCoercion(object):
    def test_coercion(self):
        class EnrichedString(text_type):
            pass

        e = Entry('title', 'url')
        e['test'] = EnrichedString("test")
        assert type(e['test']) == text_type  # pylint: disable=unidiomatic-typecheck


class TestFilterRequireField(object):
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
        assert not task.find_entry('rejected', title='Taken[2008]DvDrip[Eng]-FOO'), \
            'Taken should NOT have been rejected'
        assert task.find_entry('rejected', title='ASDFASDFASDF'), \
            'ASDFASDFASDF should have been rejected'

        task = execute_task('test2')
        assert not task.find_entry('rejected', title='Entry.S01E05.720p'), \
            'Entry should NOT have been rejected'
        assert task.find_entry('rejected', title='Entry2.is.a.Movie'), \
            'Entry2 should have been rejected'


class TestHtmlUtils(object):
    def test_decode_html(self):
        """utils decode_html"""
        from flexget.utils.tools import decode_html
        assert decode_html('&lt;&#51;') == u'<3'
        assert decode_html('&#x2500;') == u'\u2500'

    @pytest.mark.skip(reason='FAILS - DISABLED')
    def test_encode_html(self):
        """utils encode_html (FAILS - DISABLED)"""
        # why this does not encode < ?
        from flexget.utils.tools import encode_html
        print(encode_html('<3'))
        assert encode_html('<3') == '&lt;3'


class TestSetPlugin(object):
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
        assert entry['otherfield'] == ''
        assert entry['alu'] == 'alu'
        entry = task.find_entry('entries', title='Entry 2')
        assert entry['field'] is None, \
            '`field` should be None when jinja rendering fails'
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
        assert entry['title'] == 'Entry 1', 'should fall back to original value when template fails'
        assert entry['other'] is None
