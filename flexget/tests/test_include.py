from __future__ import unicode_literals, division, absolute_import

import pytest
from jinja2 import Template


class TestInclude(object):
    _config = """
        tasks:
          include_test:
            include:
            - {{ tmpfile }}
    """

    @pytest.fixture
    def config(self, tmpdir):
        f = tmpdir.mkdir('include').join('foo.yml')
        f.write("""
            mock:
            - title: foo
        """)
        return Template(self._config).render({'tmpfile': f.strpath})

    def test_include(self, execute_task):
        task = execute_task('include_test')
        assert len(task.all_entries) == 1
        assert task.find_entry(title='foo')
