class TestRegexpList:
    config = r"""
        tasks:
          regexp_list_add:
            mock:
              - {title: 'game.of.thrones.s\d{2}e\d{2}'}
            list_add:
              - regexp_list: test 1
            accept_all: yes
          regexp_list_match:
            mock:
              - {title: 'Game of Thrones S01E01 720p HDTV-FlexGet'}
            list_match:
              from:
                - regexp_list: test 1
              remove_on_match: no
          regexp_list_add_advanced:
            mock:
              - {title: 'Game of Thrones'}
            manipulate:
              - title:
                  replace:
                    regexp: '$'
                    format: ' s\\d{2}e\\d{2}'
              - title:
                  replace:
                    regexp: ' '
                    format: '.'
            list_add:
              - regexp_list: test 1
            accept_all: yes
    """

    def test_regexp_list_simple_match(self, execute_task):
        task = execute_task('regexp_list_add')
        assert len(task.accepted) == 1

        task = execute_task('regexp_list_match')
        assert len(task.accepted) == 1

    def test_regexp_list_advanced_match(self, execute_task):
        task = execute_task('regexp_list_add_advanced')
        assert len(task.accepted) == 1

        task = execute_task('regexp_list_match')
        assert len(task.accepted) == 1
