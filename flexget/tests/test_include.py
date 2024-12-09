import pytest
from jinja2 import Template


class TestInclude:
    _config = """
        tasks:
          include_test:
            include:
            - {{ tmpfile_1 }}
            - {{ tmpfile_2 }}
    """

    @pytest.fixture
    def config(self, tmp_path):
        test_dir = tmp_path.joinpath('include')
        test_dir.mkdir()
        file_1 = test_dir.joinpath('foo.yml')
        file_2 = test_dir.joinpath('baz.yml')
        file_1.write_text(
            """
            mock:
            - title: foo
        """
        )
        file_2.write_text(
            """
            mock:
            - title: baz
        """
        )
        return Template(self._config).render(
            {'tmpfile_1': file_1.as_posix(), 'tmpfile_2': file_2.as_posix()}
        )

    def test_include(self, execute_task):
        task = execute_task('include_test')
        assert len(task.all_entries) == 2
        assert task.find_entry(title='foo')
        assert task.find_entry(title='baz')


class TestIncludeChange:
    _config = """
        tasks:
          include_test:
            include:
            - {{ tmpfile_1 }}
    """

    @pytest.fixture
    def config(self, tmp_path):
        test_dir = tmp_path.joinpath('include')
        test_dir.mkdir()
        file_1 = test_dir.joinpath('foo.yml')
        file_1.write_text(
            """
            mock:
            - title: foo
        """
        )
        return Template(self._config).render({'tmpfile_1': file_1.as_posix()})

    def test_include_update(self, execute_task, manager, tmp_path):
        task = execute_task('include_test')
        assert len(task.all_entries) == 1
        assert task.find_entry(title='foo')

        # Run without change. verify task hasn't changed
        task = execute_task('include_test')
        assert not task.config_modified

        # Change file name
        test_dir = tmp_path.joinpath('include_changed')
        test_dir.mkdir()
        file_1 = test_dir.joinpath('foo.yml')
        file_1.write_text(
            """
            mock:
            - title: foo_change_1
        """
        )
        new_file = Template('{{ tmpfile_1 }}').render({'tmpfile_1': file_1.as_posix()})
        manager.config['tasks']['include_test']['include'].pop()
        manager.config['tasks']['include_test']['include'].append(new_file)

        task = execute_task('include_test')
        assert len(task.all_entries) == 1
        assert task.find_entry(title='foo_change_1')
        assert task.config_modified

        # Change file contents
        file_1.write_text(
            """
            mock:
            - title: foo_change_2
        """
        )
        task = execute_task('include_test')
        assert len(task.all_entries) == 1
        assert task.find_entry(title='foo_change_2')
        assert task.config_modified
