class TestTemplate:
    config = """
        templates:
          global:
            mock:
              - {title: 'global'}
          movies:
            mock:
              - {title: 'movies'}
          a:
            mock:
              - {title: 'a'}
            template: b
          b:
            mock:
              - {title: 'b'}

        tasks:
          test1:
            template: movies

          test2:
            template: no

          test3:
            template:
              - movies
              - no_global

          test_nested:
            template:
              - a
              - no_global
    """

    def test_preset1(self, execute_task):
        task = execute_task('test1')
        assert task.find_entry(title='global'), 'test1, preset global not applied'
        assert task.find_entry(title='movies'), 'test1, preset movies not applied'

    def test_preset2(self, execute_task):
        task = execute_task('test2')
        assert not task.find_entry(title='global'), 'test2, preset global applied'
        assert not task.find_entry(title='movies'), 'test2, preset movies applied'

    def test_preset3(self, execute_task):
        task = execute_task('test3')
        assert not task.find_entry(title='global'), 'test3, preset global applied'
        assert task.find_entry(title='movies'), 'test3, preset movies not applied'

    def test_nested(self, execute_task):
        task = execute_task('test_nested')
        assert task.find_entry(title='a'), 'Entry from preset a was not created'
        assert task.find_entry(title='b'), 'Entry from preset b was not created'
        assert len(task.entries) == 2, 'Should only have been 2 entries created'


class TestTemplateMerge:
    config = """
        templates:
          movies:
            seen_movies: strict
            imdb:
              min_score: 6.0
              min_votes: 500
              min_year: 2006
              reject_genres:
                - musical
                - music
                - biography
                - romance

        tasks:
          test:
            template: movies
            imdb:
              min_score: 6.5
              reject_genres:
                - comedy
    """

    def test_merge(self, execute_task):
        task = execute_task('test')
        assert task.config['imdb']['min_score'] == 6.5, 'float merge failed'
        assert 'comedy' in task.config['imdb']['reject_genres'], 'list merge failed'


class TestTemplateRerun:
    config = """
        templates:
          a:
            series:
            - someseries
        tasks:
          test_rerun:
            template: a
            rerun: 1
    """

    def test_rerun(self, execute_task):
        task = execute_task('test_rerun')
        assert len(task.config['series']) == 1


class TestTemplateChange:
    config = """
        templates:
          a:
            mock:
            - title: foo
        tasks:
          test_config_change:
            mock:
            - title: bar
            template: a
    """

    def test_template_change_trigger_config_change(self, execute_task, manager):
        task = execute_task('test_config_change')
        assert len(task.all_entries) == 2

        manager.config['templates']['a']['mock'].append({'title': 'baz}'})
        task = execute_task('test_config_change')
        assert task.config_modified
        assert len(task.all_entries) == 3
