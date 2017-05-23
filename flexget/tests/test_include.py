from __future__ import unicode_literals, division, absolute_import

import pytest
from jinja2 import Template


class TestInclude(object):
    _config = """
        tasks:
          include_test:
            include:
            - {{ tmpfile_1 }}
            - {{ tmpfile_2 }}
    """

    @pytest.fixture
    def config(self, tmpdir):
        test_dir = tmpdir.mkdir('include')
        file_1 = test_dir.join('foo.yml')
        file_2 = test_dir.join('baz.yml')
        file_1.write("""
            mock:
            - title: foo
        """)
        file_2.write("""
            mock:
            - title: baz
        """)
        return Template(self._config).render({'tmpfile_1': file_1.strpath, 'tmpfile_2': file_2.strpath})

    def test_include(self, execute_task):
        task = execute_task('include_test')
        assert len(task.all_entries) == 2
        assert task.find_entry(title='foo')
        assert task.find_entry(title='baz')
