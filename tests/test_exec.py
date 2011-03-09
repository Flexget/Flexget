from __future__ import with_statement
from tests import FlexGetBase
import os
import os.path


class TestExec(FlexGetBase):

    __tmp__ = True
    __yaml__ = """
        presets:
          global:
            set:
              temp_dir: '__tmp__'
        feeds:
          replace_from_entry:
            mock:
              - {title: 'replace'}
              - {title: 'replace with spaces'}
            exec: python exec.py "%(temp_dir)s" "%(title)s"
            accept_all: yes
          test_adv_format:
            mock:
              - {title: entry1, location: '/path/with spaces', quotefield: "with'quote"}
            exec:
              on_download:
                for_entries: python exec.py '%(temp_dir)s' '%(title)s' '%(location)s' '/the/final destinaton/'\
                                                  "a %(quotefield)s" '/a hybrid %(location)s'
          test_auto_escape:
            mock:
              - {title: entry2, quotes: single ' double", otherchars: '% a $a! ` *'}
            exec:
              on_download:
                for_entries: python exec.py '%(temp_dir)s' '%(title)s' %(quotes)s /start/%(quotes)s %(otherchars)s
    """

    def test_replace_from_entry(self):
        self.execute_feed('replace_from_entry')
        assert len(self.feed.accepted) == 2, "not all entries were accepted"
        for entry in self.feed.accepted:
            assert os.path.exists(os.path.join(self.__tmp__, entry['title'])), "exec.py did not create a file for %s" % entry['title']

    def test_adv_format(self):
        self.execute_feed('test_adv_format')
        for entry in self.feed.accepted:
            with open(os.path.join(self.__tmp__, entry['title']), 'r') as infile:
                line = infile.readline().rstrip('\n')
                assert line == '/path/with spaces/thefile', '%s != /path/with spaces' % line
                line = infile.readline().rstrip('\n')
                assert line == '/the/final-destinaton/', '%s != /the/final destinaton/' % line
                line = infile.readline().rstrip('\n')
                assert line == 'a with"quote', '%s != a with"quote' % line
                line = infile.readline().rstrip('\n')
                assert line == '/a hybrid /path/with spaces', '%s != /a hybrid /path/with spaces' % line

    def test_auto_escape(self):
        self.execute_feed('test_auto_escape')
        for entry in self.feed.accepted:
            with open(os.path.join(self.__tmp__, entry['title']), 'r') as infile:
                line = infile.readline().rstrip('\n')
                assert line == 'single \' double\"', '%s != single \' double\"' % line
                line = infile.readline().rstrip('\n')
                assert line == '/start/single \' double\"', '%s != /start/single \' double\"' % line
                line = infile.readline().rstrip('\n')
                assert line == '% a $a! ` *', '%s != % a $a! ` *' % line
