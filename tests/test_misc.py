import os
from tests import FlexGetBase
from nose.plugins.attrib import attr
from nose.tools import raises
from flexget.feed import EntryUnicodeError, Entry


class TestDisableBuiltins(FlexGetBase):
    """
        Quick a hack, test disable functionality by checking if seen filtering (builtin) is working
    """

    __yaml__ = """
        feeds:
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
        return
        
        self.execute_feed('test')
        assert self.feed.find_entry(title='dupe1') and self.feed.find_entry(title='dupe2'), 'disable_builtins is not working?'


class TestInputHtml(FlexGetBase):

    __yaml__ = """
        feeds:
          test:
            html: http://download.flexget.com/
    """

    def test_parsing(self):
        self.execute_feed('test')
        assert self.feed.entries, 'did not produce entries'


class TestPriority(FlexGetBase):

    __yaml__ = """
        feeds:
          test:
            mock:
              - {title: 'Smoke'}
            accept_all: yes
            plugin_priority:
              accept_all: 100
    """

    def test_smoke(self):
        self.execute_feed('test')
        assert self.feed.entries, 'no entries created'


class TestImmortal(FlexGetBase):

    __yaml__ = """
        feeds:
          test:
            mock:
              - {title: 'title1', immortal: yes}
              - {title: 'title2'}
            regexp:
              reject:
                - .*
    """

    def test_immortal(self):
        self.execute_feed('test')
        assert self.feed.find_entry(title='title1'), 'rejected immortal entry'
        assert not self.feed.find_entry(title='title2'), 'did not reject mortal'


class TestDownload(FlexGetBase):

    __yaml__ = """
        feeds:
          test:
            mock:
              - title: README
                url: http://svn.flexget.com/trunk/bootstrap.py
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
        FlexGetBase.tearDown(self)
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
        if os.path.exists(self.testfile):
            os.remove(self.testfile)
        # executes feed and downloads the file
        self.execute_feed('test')
        assert self.feed.entries[0]['output'], 'output missing?'
        self.testfile = self.feed.entries[0]['output']
        assert os.path.exists(self.testfile), 'download file does not exists'


class TestMetainfoQuality(FlexGetBase):

    __yaml__ = """
        feeds:
          test:
            mock:
              - {title: 'FooBar.S01E02.720p.HDTV'}
              - {title: 'ShowB.S04E19.Name of Ep.720p.WEB-DL.DD5.1.H.264'}
    """

    def test_quality(self):
        self.execute_feed('test')
        entry = self.feed.find_entry(title='FooBar.S01E02.720p.HDTV')
        assert entry, 'entry not found?'
        assert 'quality' in entry, 'failed to pick up quality'
        assert entry['quality'] == '720p', 'picked up wrong quality %s' % entry.get('quality', None)
        entry = self.feed.find_entry(title='ShowB.S04E19.Name of Ep.720p.WEB-DL.DD5.1.H.264')
        assert entry, 'entry not found?'
        assert 'quality' in entry, 'failed to pick up quality'
        assert entry['quality'] == 'web-dl', 'picked up wrong quality %s' % entry.get('quality', None)


class TestFilterQuality(FlexGetBase):

    __yaml__ = """
        feeds:
          test:
            mock:
              - {title: 'Smoke.720p'}
              - {title: 'Smoke.HDTV'}
              - {title: 'Smoke.cam'}
            quality:
              - hdtv
              - 720p
            accept_all: yes
    """

    def test_quality(self):
        self.execute_feed('test')
        entry = self.feed.find_entry(title='Smoke.cam')
        assert entry, 'entry not found?'
        assert entry in self.feed.rejected, 'cam quality should be rejected'
        
        entry = self.feed.find_entry(title='Smoke.720p')
        assert entry, 'entry not found?'
        assert entry in self.feed.accepted, '720p should be accepted'
        assert len(self.feed.rejected) == 1, 'wrong number of entries rejected'
        assert len(self.feed.accepted) == 2, 'wrong number of entries accepted'


class TestEntryUnicodeError(FlexGetBase):

    @raises(EntryUnicodeError)
    def test_encoding(self):
        e = Entry('title', 'url')
        e['invalid'] = '\x8e'


class TestFilterRequireField(FlexGetBase):

    __yaml__ = """
        feeds:
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
        self.execute_feed('test')
        assert not self.feed.find_entry('rejected', title='Taken[2008]DvDrip[Eng]-FOO'), \
            'Taken should NOT have been rejected'
        assert self.feed.find_entry('rejected', title='ASDFASDFASDF'), \
            'ASDFASDFASDF should have been rejected'

        self.execute_feed('test2')
        assert not self.feed.find_entry('rejected', title='Entry.S01E05.720p'), \
            'Entry should NOT have been rejected'
        assert self.feed.find_entry('rejected', title='Entry2.is.a.Movie'), \
            'Entry2 should have been rejected'
