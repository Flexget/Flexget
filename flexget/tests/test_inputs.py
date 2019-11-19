class TestInputs:
    config = """
        tasks:
          test_inputs:
            inputs:
              - mock:
                  - {title: 'title1', url: 'http://url1'}
              - mock:
                  - {title: 'title2', url: 'http://url2'}
          test_no_dupes:
            inputs:
              - mock:
                  - {title: 'title1a', url: 'http://url1'}
                  - {title: 'title2', url: 'http://url2a'}
              - mock:
                  - {title: 'title1b', url: 'http://url1'}
                  - {title: 'title1c', url: 'http://other', urls: ['http://url1']}
                  - {title: 'title2', url: 'http://url2b'}
          test_no_url:
            inputs:
              - mock:
                  - title: title1
              - mock:
                  - title: title2
    """

    def test_inputs(self, execute_task):
        task = execute_task('test_inputs')
        assert len(task.entries) == 2, 'Should have created 2 entries'

    def test_no_dupes(self, execute_task):
        task = execute_task('test_no_dupes')
        assert len(task.entries) == 2, 'Should only have created 2 entries'
        assert task.find_entry(title='title1a'), 'title1a should be in entries'
        assert task.find_entry(title='title2'), 'title2 should be in entries'
