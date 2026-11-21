from io import StringIO
from pathlib import Path

from flexget.manager import get_parser
from flexget.plugins.cli import templates as templates_cli
from flexget.terminal import capture_console


class TestTemplatesCli:
    config = """
        tasks: {}
    """

    def test_list_templates_with_non_ascii_content(self, manager, monkeypatch):
        """Template files are UTF-8, like Jinja reads them, whatever the locale encoding is."""
        template_dir = manager.config_base / 'templates' / 'task'
        template_dir.mkdir(parents=True)
        content = 'Hello Łukasz ✨ {{ task.name }}'
        (template_dir / 'unicode_test.template').write_bytes(content.encode('utf-8'))

        def locale_open(file, mode='r', *args, **kwargs):
            # Simulate a non-UTF-8 locale (Windows cp1252, cp949, ...) on any OS
            if 'b' not in mode and len(args) < 2 and 'encoding' not in kwargs:
                kwargs['encoding'] = 'cp1252'
            return Path(file).open(mode, *args, **kwargs)

        monkeypatch.setattr(templates_cli, 'open', locale_open, raising=False)

        options = get_parser().parse_args(['templates', '--name', 'unicode_test'])
        buffer = StringIO()
        with capture_console(buffer):
            manager.handle_cli(options=options)
        output = buffer.getvalue()
        assert 'unicode_test' in output
        assert 'Łukasz ✨' in output
