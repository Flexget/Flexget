from __future__ import unicode_literals, division, absolute_import
import os
import stat
from tests import FlexGetBase
from nose.plugins.attrib import attr
from nose.tools import raises
from flexget.entry import EntryUnicodeError, Entry


class TestDisableBuiltins(FlexGetBase):
    """
        Quick a hack, test disable functionality by checking if seen filtering (builtin) is working
    """

    __yaml__ = """
        tasks:
            test:
                mock:
                    - {title: 'dupe1', url: 'http://localhost/dupe', 'imdb_score': 5}
                    - {title: 'dupe2', url: 'http://localhost/dupe', 'imdb_score': 5}
                disable_builtins: true

            test2:
                mock:
                    - {title: 'dupe1', url: 'http://localhost/dupe', 'imdb_score': 5, description: 'http://www.imdb.com/title/tt0409459/'}
                    - {title: 'dupe2', url: 'http://localhost/dupe', 'imdb_score': 5}
                disable_builtins:
                    - seen
                    - cli_config
    """

    def test_disable_builtins(self):
        self.execute_task('test')
        assert self.task.find_entry(title='dupe1') and self.task.find_entry(title='dupe2'), 'disable_builtins is not working?'


class TestInputHtml(FlexGetBase):

    __yaml__ = """
        tasks:
          test:
            html: http://download.flexget.com/
    """

    @attr(online=True)
    def test_parsing(self):
        self.execute_task('test')
        assert self.task.entries, 'did not produce entries'


class TestPriority(FlexGetBase):

    __yaml__ = """
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

    def test_smoke(self):
        self.execute_task('test')
        assert self.task.accepted, 'set plugin should have changed quality before quality plugin was run'
        self.execute_task('test2')
        assert self.task.rejected, 'quality plugin should have rejected Smoke as hdtv'


class TestImmortal(FlexGetBase):

    __yaml__ = """
        tasks:
          test:
            mock:
              - {title: 'title1', immortal: yes}
              - {title: 'title2'}
            regexp:
              reject:
                - .*
    """

    def test_immortal(self):
        self.execute_task('test')
        assert self.task.find_entry(title='title1'), 'rejected immortal entry'
        assert not self.task.find_entry(title='title2'), 'did not reject mortal'


class TestDownload(FlexGetBase):

    __yaml__ = """
        tasks:
          test:
            mock:
              - title: README
                url: https://github.com/Flexget/Flexget/raw/master/README.rst
                filename: flexget_test_data
            accept_all: true
            download:
              path: ~/
              fail_html: no
    """

    def __init__(self):
        self.testfile = None
        FlexGetBase.__init__(self)

    def teardown(self):
        FlexGetBase.teardown(self)
        if hasattr(self, 'testfile') and os.path.exists(self.testfile):
            os.remove(self.testfile)
        temp_dir = os.path.join(self.manager.config_base, 'temp')
        if os.path.exists(temp_dir) and os.path.isdir(temp_dir):
            os.rmdir(temp_dir)

    @attr(online=True)
    def test_download(self):
        # NOTE: what the hell is .obj and where it comes from?
        # Re: seems to come from python mimetype detection in download plugin ...
        # Re Re: Implemented in such way that extension does not matter?
        self.testfile = os.path.expanduser('~/flexget_test_data.obj')
        # A little convoluted, but you have to set the umask in order to have
        # the current value returned to you
        curr_umask = os.umask(0)
        tmp_umask = os.umask(curr_umask)
        if os.path.exists(self.testfile):
            os.remove(self.testfile)
        # executes task and downloads the file
        self.execute_task('test')
        assert self.task.entries[0]['output'], 'output missing?'
        self.testfile = self.task.entries[0]['output']
        assert os.path.exists(self.testfile), 'download file does not exists'
        testfile_stat = os.stat(self.testfile)
        modes_equal = 666 - int(oct(curr_umask)) == \
                      int(oct(stat.S_IMODE(testfile_stat.st_mode)))
        assert modes_equal, 'download file mode not honoring umask'


class TestEntryUnicodeError(object):

    @raises(EntryUnicodeError)
    def test_encoding(self):
        e = Entry('title', 'url')
        e['invalid'] = b'\x8e'


class TestFilterRequireField(FlexGetBase):

    __yaml__ = """
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

    def test_field_required(self):
        self.execute_task('test')
        assert not self.task.find_entry('rejected', title='Taken[2008]DvDrip[Eng]-FOO'), \
            'Taken should NOT have been rejected'
        assert self.task.find_entry('rejected', title='ASDFASDFASDF'), \
            'ASDFASDFASDF should have been rejected'

        self.execute_task('test2')
        assert not self.task.find_entry('rejected', title='Entry.S01E05.720p'), \
            'Entry should NOT have been rejected'
        assert self.task.find_entry('rejected', title='Entry2.is.a.Movie'), \
            'Entry2 should have been rejected'


class TestHtmlUtils(object):

    def test_decode_html(self):
        """utils decode_html"""
        from flexget.utils.tools import decode_html
        assert decode_html('&lt;&#51;') == u'<3'
        assert decode_html('&#x2500;') == u'\u2500'

    def test_encode_html(self):
        """utils encode_html (FAILS - DISABLED)"""
        return

        # why this does not encode < ?
        from flexget.utils.tools import encode_html
        print encode_html('<3')
        assert encode_html('<3') == '&lt;3'


class TestSetPlugin(FlexGetBase):

    __yaml__ = """
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
    """

    def test_set(self):
        self.execute_task('test')
        entry = self.task.find_entry('entries', title='Entry 1')
        assert entry['thefield'] == 'TheValue'
        assert entry['otherfield'] == 3.0

    def test_jinja(self):
        self.execute_task('test_jinja')
        entry = self.task.find_entry('entries', title='Entry 1')
        assert entry['field'] == 'The VALUE'
        assert entry['otherfield'] == ''
        assert entry['alu'] == 'alu'
        entry = self.task.find_entry('entries', title='Entry 2')
        assert 'field' not in entry,\
                '`field` should not have been created when jinja rendering fails'
        assert entry['otherfield'] == 'no series'
