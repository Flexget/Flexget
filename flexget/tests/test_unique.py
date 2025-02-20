class TestUniques:
    config = """
        templates:
          global:
            # just cleans log a bit ..
            disable:
              - seen

        tasks:
          single_field:
            mock:
              - {title: 'bla1', episode_id: 1, series_id: 1, quality: '720p'}
              - {title: 'bla2', episode_id: 1, series_id: 1}
              - {title: 'bla3', episode_id: 1, series_id: 2, quality: '720p'}
            unique:
              action: reject
              field: episode_id

          multi_field:
            mock:
              - {title: 'bla1', episode_id: 1, series_id: 1, quality: '720p'}
              - {title: 'bla2', episode_id: 1, series_id: 1}
              - {title: 'bla3', episode_id: 1, series_id: 2, quality: '720p'}
            unique:
              field:
              - episode_id
              - series_id

          missing_field:
            mock:
              - {title: 'bla1', episode_id: 1, series_id: 1, quality: '720p'}
              - {title: 'bla2', episode_id: 1, series_id: 1}
              - {title: 'bla3', episode_id: 1, series_id: 2, quality: '720p'}
            unique:
              field:
              - episode_id
              - quality

    """

    def test_single_field(self, execute_task):
        """Unique plugin: Filter by single field."""
        task = execute_task('single_field')
        assert len(task.rejected) == 2, 'Should reject 2 entries'
        assert [e['title'] for e in task.rejected] == ['bla2', 'bla3'], 'should reject bla2,bla3'

    def test_multi_field(self, execute_task):
        """Unique plugin: Filter by multiple fields."""
        task = execute_task('multi_field')
        assert len(task.rejected) == 1, 'should reject 1 entries'
        assert task.rejected[0]['title'] == 'bla2', 'should reject bla2'

    def test_missing_field(self, execute_task):
        """Unique plugin: Ensure we ignore entries with missing fields."""
        task = execute_task('missing_field')
        assert len(task.rejected) == 1, 'should reject 1 entires'
        assert task.rejected[0]['title'] == 'bla3', 'should reject bla3'
