import pytest
from jinja2 import Template
from json import dumps


class TestIncludes(object):
    _config = """
        tasks: !include_named {{include_tasks}}
    """

    @pytest.fixture
    def config(self, tmpdir):
        """
        Adding a example of each type of include

        include - includes a file or dir (search subdirs). Includes the files contents
        include_list - includes a file or dir (search subdirs). Includes the files contents in list
        include_named - includes a file or dir (search subdirs). Includes the file contents, property is the file name
        include_named_list - includes a file or dir (search subdirs). Includes the file contents, property is the file name in list

        """

        # Folder for extras
        extra_dir = tmpdir.mkdir('extras')
        accept_all = extra_dir.join('accept_all.yaml')
        accept_all.write('yes')
        accept_all_path = accept_all.strpath

        regexp_dir = extra_dir.mkdir('regexp')
        regexp_actions1 = regexp_dir.join('regexp_actions1.yaml')
        regexp_actions1.write(
            """
            reject:
              - input4
            """
        )
        regexp_actions2 = regexp_dir.join('regexp_actions2.yaml')
        regexp_actions2.write(
            """
            accept:
              - input1
              - input2
            """
        )

        # Folder for all the lists
        lists_dir = tmpdir.mkdir('lists')

        # Folder for lists to be used named
        input_named_list = lists_dir.mkdir('input_named_list')
        input_named1 = input_named_list.mkdir('mock1')
        input_named2 = input_named_list.mkdir('mock2')

        # Folder for lists to be used not named
        input_list = lists_dir.mkdir('input_list')
        input1 = input_list.mkdir('src1')
        input2 = input_list.mkdir('src2')

        #################################################################
        # Test of input names list in list mode
        input_lists = input_named1.join('mock.yaml')
        input_lists.write(
            """
            - {'title':'input1','url':'mock://input1'}
            - {'title':'input2','url':'mock://input2'}
            """
        )

        input_lists = input_named2.join('mock.yaml')
        input_lists.write(
            """
            - {'title':'input3','url':'mock://input3'}
            """
        )

        input_list_named_path = input_named_list.strpath

        #################################################################
        # Test of input list in list mode
        input_lists = input1.join('src1.yaml')
        input_lists.write(
            """
            - mock:
                - {'title':'input1','url':'mock://input1'}
                - {'title':'input2','url':'mock://input2'}
            - mock:
                - {'title':'input3','url':'mock://input3'}
                - {'title':'input4','url':'mock://input4'}
            """
        )

        input_lists = input2.join('src2.yaml')
        input_lists.write(
            """
            mock:
              - {'title':'input5','url':'mock://input5'}
            """
        )

        input_list_path = input_list.strpath

        # Test of Included named (Files is the name of the property, task)
        tasks_dir = tmpdir.mkdir('tasks')

        # Test Include Named (include_named and include_named_list)
        task_dir = tasks_dir.mkdir("task_subfolder")
        task = task_dir.join('task_named.yaml')
        task.write(
            f"""
            inputs:  !include_named_list {input_list_named_path}
            accept_all: !include {accept_all_path}
            """
        )

        # Test Include (include and include_list)
        task = tasks_dir.join('task_normal.yaml')
        task.write(
            f"""
            inputs:  !include_list {input_list_path}
            regexp: !include {regexp_dir}
            """
        )

        return Template(self._config).render({'include_tasks': tasks_dir.strpath})

    def test_include(self, execute_task):
        task = execute_task('task_normal')
        json = dumps(task.config)
        assert len(task.accepted) == 2
        assert len(task.rejected) == 1
        assert len(task.undecided) == 2

        assert (
            json
            == '{"inputs": [{"mock": [{"title": "input1", "url": "mock://input1"}, {"title": "input2", "url": "mock://input2"}]}, {"mock": [{"title": "input3", "url": "mock://input3"}, {"title": "input4", "url": "mock://input4"}]}, {"mock": [{"title": "input5", "url": "mock://input5"}]}], "regexp": {"reject": ["input4"], "accept": ["input1", "input2"]}}'
        )

    def test_include_named(self, execute_task):
        task = execute_task('task_named')
        json = dumps(task.config)
        assert len(task.accepted) == 3
        assert (
            json
            == '{"inputs": [{"mock": [{"title": "input1", "url": "mock://input1"}, {"title": "input2", "url": "mock://input2"}, {"title": "input3", "url": "mock://input3"}]}], "accept_all": true}'
        )
