import pytest


class TestAsciifyFilter:
    config = """
        tasks:
          asscify_me:
            mock:
              - {"title":"[My](Tìtlê)-ìs a' me^ss", "url":"mock://local" }
                
            accept_all: yes
                
            set:
              title: "{{title|asciify|replace('is','is not')}}"
    """

    def test_asciify_me(self, execute_task):
        task = execute_task('asscify_me')

        assert len(task.accepted) == 1
        assert task.accepted[0]['title'] == 'My Title is not a mess'