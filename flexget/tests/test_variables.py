import pytest

from flexget.components.variables.variables import Variables
from flexget.event import fire_event
from flexget.manager import Session


class TestVariablesFromFile:
    config = """
        variables: __tmp__/variables.yml
        tasks:
          test_variable_from_file:
            mock:
              - { title: 'test', location: 'http://mock'}
            if:
              - '{? test_variable ?}': accept

          test_variables_alongside_jinja:
            mock:
            - title: title 1
              entry_var: foo
            set:
              a_field: first {?bar_var?} then {{entry_var|default("shouldn't happen")}} {{fake_field|default("end")}}
            accept_all: yes
    """

    @pytest.mark.filecopy('variables.yml', '__tmp__/variables.yml')
    def test_variable_from_file(self, execute_task, manager):
        task = execute_task('test_variable_from_file')
        assert len(task.accepted) == 1

    @pytest.mark.filecopy('variables.yml', '__tmp__/variables.yml')
    def test_variables_alongside_jinja(self, execute_task):
        task = execute_task('test_variables_alongside_jinja')
        assert len(task.accepted) == 1
        assert task.accepted[0]['a_field'] == 'first bar then foo end'


class TestVariablesFromConfig:
    config = """
      variables:
        mock_entry_list:
        - title: a
        - title: b
        integer: 2
      tasks:
        test_int_var:
          mock:
          - title: a
          - title: b
          - title: c
          accept_all: yes
          limit_new: "{? integer ?}"
        test_var_mock:
          mock: "{? mock_entry_list ?}"
    """

    def test_complex_var(self, execute_task):
        task = execute_task('test_var_mock')
        assert len(task.all_entries) == 2
        assert task.all_entries[1]['title'] == 'b'

    def test_int_var(self, execute_task):
        task = execute_task('test_int_var')
        assert len(task.all_entries) == 3
        assert len(task.accepted) == 2


class TestVariablesFromDB:
    config = """
        variables: yes
        tasks:
          test_variable_from_db:
            mock:
              - { title: 'test', location: 'http://mock'}
            if:
              - '{? test_variable_db ?}': accept

    """

    def test_variable_from_db(self, execute_task, manager):
        with Session() as session:
            s = Variables(variables={'test_variable_db': True})
            session.add(s)

        fire_event('manager.before_config_validate', manager.config, manager)

        task = execute_task('test_variable_from_db')
        assert len(task.accepted) == 1
