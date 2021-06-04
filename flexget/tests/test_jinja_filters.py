import pytest


class TestJinjaFilters:
    config = """
        tasks:
          stripyear:
            mock:
              - {"title":"The Matrix (1999)", "url":"mock://local1" }
              - {"title":"The Matrix", "url":"mock://local2" }
              - {"title":"The Matrix 1999", "url":"mock://local3" }
              - {"title":"2000", "url":"mock://local3" }
              - {"title":"2000 (2020)", "url":"mock://local4" }
              - {"title":"2000 2020", "url":"mock://local5" }
                
            accept_all: yes
                
            set:
              name: "{{title|strip_year}}"
              year: "{{title|get_year}}"
    """

    def test_stripyear(self, execute_task):
        task = execute_task('stripyear')

        assert len(task.accepted) == 6
        assert task.accepted[0]['name'] == 'The Matrix'
        assert task.accepted[0]['year'] == 1999

        assert task.accepted[1]['name'] == 'The Matrix'
        assert task.accepted[1]['year'] is None

        assert task.accepted[2]['name'] == 'The Matrix'
        assert task.accepted[2]['year'] == 1999

        assert task.accepted[3]['name'] == 2000
        assert task.accepted[3]['year'] is None

        assert task.accepted[4]['name'] == 2000
        assert task.accepted[4]['year'] == 2020

        assert task.accepted[5]['name'] == 2000
        assert task.accepted[5]['year'] == 2020
