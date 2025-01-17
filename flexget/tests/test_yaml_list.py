import pytest
from jinja2 import Template


class TestYamlLists:
    _config = """
        tasks:
          yaml_check_list1:
            disable: seen
            accept_all: yes
            yaml_list: '{{yaml_dir}}/yaml_list1.yaml'

          yaml_list_create:
            disable: seen
            mock:
              - {'title':'My Entry 1 1080p HDTV','url':'mock://myentry1', 'data':'myentry1', 'data2':'trash1'}
              - {'title':'My Entry 2 1080p HDTV','url':'mock://myentry2', 'data':'myentry2', 'data2':'trash2'}
              - {'title':'My Entry 3 1080p HDTV','url':'mock://myentry3', 'data':'myentry3', 'data2':'trash3'}

            accept_all: yes
            list_add:
              - yaml_list:
                  fields:
                    - data
                    - quality
                  path: '{{yaml_dir}}/yaml_list1.yaml'


          yaml_list_remove:
            disable: seen
            mock:
              - {'title':'My Entry 1 1080p HDTV','url':'mock://myentry1'}

            accept_all: yes
            list_remove:
              - yaml_list: '{{yaml_dir}}/yaml_list1.yaml'

          yaml_list_match:
            disable: seen
            mock:
              - {'title':'My Entry 2 1080p HDTV','url':'mock://myentry2', 'data':'myentry2'}
              - {'title':'My Entry 3 1080p HDTV','url':'mock://myentry3', 'data':'myentry3'}

            list_match:
              remove_on_match: no
              from:
                - yaml_list: '{{yaml_dir}}/yaml_list1.yaml'

          yaml_list_fields:
            disable: seen
            accept_all: yes
            mock:
              - {'title':'My Entry 1 1080p HDTV','url':'mock://myentry1', 'data':'myentry1'}
              - {'title':'My Entry 2 1080p HDTV','url':'mock://myentry2', 'data':'myentry2'}

            set:
              newfield: 'new'

            list_add:
              - yaml_list:
                  path: '{{yaml_dir}}/yaml_list1.yaml'
                  fields:
                    - newfield

          yaml_list_update:
            disable: seen
            accept_all: yes
            mock:
              - {'title':'My Entry 1 1080p HDTV','new':'teste1','trash':'trash1'}
              - {'title':'My Entry 2 1080p HDTV','new':'teste2','trash':'trash2'}

            list_add:
              - yaml_list:
                  path: '{{yaml_dir}}/yaml_list1.yaml'
                  fields:
                    - new

          yaml_list_load:
            disable: seen
            accept_all: yes
            yaml_list: '{{yaml_dir}}/yaml_list1.yaml'
    """

    @pytest.fixture
    def config(self, tmp_path):
        """
        Prepare config
        """

        yaml_dir = tmp_path.joinpath('yaml_lists')
        yaml_dir.mkdir()

        return Template(self._config).render({'yaml_dir': yaml_dir.as_posix()})

    def test_list_create(self, execute_task):
        task = execute_task('yaml_list_create')
        assert len(task.accepted) == 3

        # Checks if list is ok
        task = execute_task('yaml_check_list1')
        assert len(task.accepted) == 3

        # Ensures that data is not lost
        assert task.accepted[0]['data'] == 'myentry1'
        assert task.accepted[1]['data'] == 'myentry2'
        assert task.accepted[2]['data'] == 'myentry3'

    def test_list_remove(self, execute_task):
        task = execute_task('yaml_list_create')
        assert len(task.accepted) == 3

        task = execute_task('yaml_list_remove')
        assert len(task.accepted) == 1

        # Checks if list is ok
        task = execute_task('yaml_check_list1')
        assert len(task.accepted) == 2

        # Checks matched
        assert task.accepted[0]['title'] == 'My Entry 2 1080p HDTV'
        assert task.accepted[1]['title'] == 'My Entry 3 1080p HDTV'

    def test_list_match(self, execute_task):
        task = execute_task('yaml_list_create')
        assert len(task.accepted) == 3

        task = execute_task('yaml_list_match')
        assert len(task.accepted) == 2

        # Checks matched
        assert task.accepted[0]['title'] == 'My Entry 2 1080p HDTV'
        assert task.accepted[1]['title'] == 'My Entry 3 1080p HDTV'

    def test_list_limited_fields(self, execute_task):
        task = execute_task('yaml_list_fields')
        assert len(task.accepted) == 2

        # Check old field
        assert 'data' in task.accepted[0]
        assert 'data' in task.accepted[1]

        task = execute_task('yaml_check_list1')
        assert len(task.accepted) == 2

        # Checks matched
        assert task.accepted[0]['title'] == 'My Entry 1 1080p HDTV'
        assert task.accepted[1]['title'] == 'My Entry 2 1080p HDTV'

        # Check no old field
        assert 'data' not in task.accepted[0]
        assert 'data' not in task.accepted[1]

        # Check ok field
        assert task.accepted[0]['newfield'] == 'new'
        assert task.accepted[1]['newfield'] == 'new'

    def test_list_update(self, execute_task):
        task = execute_task('yaml_list_create')
        assert len(task.accepted) == 3

        task = execute_task('yaml_list_update')
        assert len(task.accepted) == 2

        task = execute_task('yaml_list_load')
        assert len(task.accepted) == 3

        # Checks matched
        assert task.accepted[0]['title'] == 'My Entry 1 1080p HDTV'
        assert task.accepted[1]['title'] == 'My Entry 2 1080p HDTV'
        assert task.accepted[2]['title'] == 'My Entry 3 1080p HDTV'

        # Checks update
        assert task.accepted[0]['new'] == 'teste1'
        assert task.accepted[1]['new'] == 'teste2'
        assert 'new' not in task.accepted[2]

        # Checks not update
        assert 'trash' not in task.accepted[0]
        assert 'trash' not in task.accepted[1]
