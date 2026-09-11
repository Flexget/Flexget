import sys
from pathlib import Path


class TestExec:
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
        + """"/the/final destination/" "a {{quotefield}}" "/a hybrid{{location}}"
          test_auto_escape:
            mock:
              - {title: entry2, quotes: single ' double", otherchars: '% a $a! ` *'}
            exec:
              auto_escape: yes
              on_output:
                for_entries: """
        + sys.executable
        + """ exec.py "{{temp_dir}}" "{{title}}" {{quotes}} /start/{{quotes}} {{otherchars}}
          test_auto_escape_injection:
            mock:
              - {title: 'inject `touch __tmp__/pwned_backtick` and $(touch __tmp__/pwned_subshell); echo done'}
            exec:
              auto_escape: yes
              on_output:
                for_entries: """
        + sys.executable
        + """ exec.py "{{temp_dir}}" result {{title}}
          test_shell_quote_filter_injection:
            mock:
              - {title: 'inject `touch __tmp__/pwned_backtick2` and $(touch __tmp__/pwned_subshell2); echo done'}
            exec:
              on_output:
                for_entries: """
        + sys.executable
        + """ exec.py "{{temp_dir}}" result {{title|shell_quote}}
    """
    )

    def test_replace_from_entry(self, execute_task, tmp_path):
        task = execute_task('replace_from_entry')
        assert len(task.accepted) == 2, 'not all entries were accepted'
        for entry in task.accepted:
            assert (tmp_path / entry['title']).exists(), (
                'exec.py did not create a file for {}'.format(entry['title'])
            )

    def test_adv_format(self, execute_task, tmp_path):
        task = execute_task('test_adv_format')
        for entry in task.accepted:
            with (tmp_path / entry['title']).open('r') as infile:
                line = infile.readline().rstrip('\n')
                assert Path(line) == Path('/path/with spaces'), f'{line} != /path/with spaces'
                line = infile.readline().rstrip('\n')
                assert line == '/the/final destination/', f'{line} != /the/final destination/'
                line = infile.readline().rstrip('\n')
                assert line == "a with'quote", f"{line} != a with'quote"
                line = infile.readline().rstrip('\n')
                assert Path(line) == Path('/a hybrid/path/with spaces'), (
                    f'{line} != /a hybrid/path/with spaces'
                )

    def test_auto_escape(self, execute_task, tmp_path):
        task = execute_task('test_auto_escape')
        for entry in task.accepted:
            with (tmp_path / entry['title']).open() as infile:
                lines = infile.read().splitlines()
            assert lines[0] == entry['quotes'], f'{lines[0]!r} != {entry["quotes"]!r}'
            assert lines[1] == '/start/' + entry['quotes']
            assert lines[2] == entry['otherchars']

    def test_auto_escape_blocks_injection(self, execute_task, tmp_path):
        task = execute_task('test_auto_escape_injection')
        assert len(task.accepted) == 1
        entry = task.accepted[0]
        with (tmp_path / 'result').open() as infile:
            line = infile.readline().rstrip('\n')
        assert line == entry['title'], (
            'malicious title was not passed through as one safe argument'
        )
        assert not (tmp_path / 'pwned_backtick').exists(), (
            'backtick command substitution executed!'
        )
        assert not (tmp_path / 'pwned_subshell').exists(), '$() command substitution executed!'

    def test_shell_quote_filter_blocks_injection(self, execute_task, tmp_path):
        task = execute_task('test_shell_quote_filter_injection')
        assert len(task.accepted) == 1
        entry = task.accepted[0]
        with (tmp_path / 'result').open() as infile:
            line = infile.readline().rstrip('\n')
        assert line == entry['title'], (
            'malicious title was not passed through as one safe argument'
        )
        assert not (tmp_path / 'pwned_backtick2').exists(), (
            'backtick command substitution executed!'
        )
        assert not (tmp_path / 'pwned_subshell2').exists(), '$() command substitution executed!'
