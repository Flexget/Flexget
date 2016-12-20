from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import pytest

from flexget.event import fire_event
from flexget.manager import Session
from flexget.plugins.modify.variables import Variables


@pytest.mark.usefixtures('tmpdir')
class TestVariablesFromFile(object):
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
              a_field: first {? bar_var ?} then {{ entry_var|default("shouldn't happen") }}
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
        assert task.accepted[0]['a_field'] == 'first bar then foo'

class TestVariablesFromDB(object):
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
