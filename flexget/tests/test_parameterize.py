from __future__ import absolute_import, division, unicode_literals

from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin


class TestParameterize(object):
    config = """
        tasks:
          test:
            parameterize:
              plugin:
                mock:
                - title: "{{title_field}}"
                  other_field: "{{other_field_field}}"
              using:
                mock:
                - title: e1
                  title_field: entry 1
                  other_field_field: field 1
                - title: e2
                  title_field: entry 2
                  other_field_field: field 2
    """

    def test_parameterize(self, manager, execute_task):
        task = execute_task('test')
        assert len(task.entries) == 2, 'Should have created entries'
        e1 = task.find_entry(title='entry 1')
        assert e1
        assert e1['other_field'] == 'field 1'
