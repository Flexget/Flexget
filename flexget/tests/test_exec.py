import os
import sys

import pytest


class TestExec:
    __tmp__ = True
    config = (
        """
        templates:
          global:
            set:
              temp_dir: '__tmp__'
            accept_all: yes
        tasks:
          replace_from_entry:
            mock:
              - {title: 'replace'}
              - {title: 'replace with spaces'}
            exec: """
        + sys.executable
        + """ exec.py "{{temp_dir}}" "{{title}}"
          test_adv_format:
            mock:
              - {title: entry1, location: '/path/with spaces', quotefield: "with'quote"}
            exec:
              on_output:
                for_entries: """
        + sys.executable
        + """ exec.py "{{temp_dir}}" "{{title}}" "{{location}}" """
        + """"/the/final destinaton/" "a {{quotefield}}" "/a hybrid{{location}}"
          test_auto_escape:
            mock:
              - {title: entry2, quotes: single ' double", otherchars: '% a $a! ` *'}
            exec:
              auto_escape: yes
              on_output:
                for_entries: """
        + sys.executable
        + """ exec.py "{{temp_dir}}" "{{title}}" "{{quotes}}" "/start/{{quotes}}" "{{otherchars}}"
    """
    )

    def test_replace_from_entry(self, execute_task, tmpdir):
        task = execute_task('replace_from_entry')
        assert len(task.accepted) == 2, "not all entries were accepted"
        for entry in task.accepted:
            assert tmpdir.join(entry['title']).exists(), (
                "exec.py did not create a file for %s" % entry['title']
            )

    def test_adv_format(self, execute_task, tmpdir):
        task = execute_task('test_adv_format')
        for entry in task.accepted:
            with tmpdir.join(entry['title']).open('r') as infile:
                line = infile.readline().rstrip('\n')
                assert line == '/path/with spaces', '%s != /path/with spaces' % line
                line = infile.readline().rstrip('\n')
                assert line == '/the/final destinaton/', '%s != /the/final destinaton/' % line
                line = infile.readline().rstrip('\n')
                assert line == 'a with\'quote', '%s != a with\'quote' % line
                line = infile.readline().rstrip('\n')
                assert line == '/a hybrid/path/with spaces', (
                    '%s != /a hybrid/path/with spaces' % line
                )

    # TODO: This doesn't work on linux.
    @pytest.mark.skip(reason='This doesn\'t work on linux')
    def test_auto_escape(self, execute_task):
        task = execute_task('test_auto_escape')
        for entry in task.accepted:
            with open(os.path.join(self.__tmp__, entry['title']), 'r') as infile:
                line = infile.readline().rstrip('\n')
                assert line == 'single \' double\"', '%s != single \' double\"' % line
                line = infile.readline().rstrip('\n')
                assert line == '/start/single \' double\"', (
                    '%s != /start/single \' double\"' % line
                )
                line = infile.readline().rstrip('\n')
                assert line == '% a $a! ` *', '%s != % a $a! ` *' % line
