class TestAsciifyFilter:
    config = """
        tasks:
          asscify_me:
            mock:
              - {"title":"[My](Tìtlê)-ìs a' me^ss", "url":"mock://local" }

            accept_all: yes

            set:
              title1: "{{title|asciify|replace('is','is still')}}"
              title2: "{{title|strip_symbols|replace('ìs','ìs still')}}"
              title3: "{{title|asciify|strip_symbols|replace('is','is not')}}"
    """

    def test_asciify_me(self, execute_task):
        task = execute_task('asscify_me')

        assert len(task.accepted) == 1
        assert task.accepted[0]['title1'] == '[My](Title)-is still a\' me^ss'
        assert task.accepted[0]['title2'] == 'My Tìtlê ìs still a mess'
        assert task.accepted[0]['title3'] == 'My Title is not a mess'
