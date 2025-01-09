class TestUrlfix:
    config = """
        tasks:
          test:
            mock:
              - {title: 'Test', url: 'http://localhost/foo?bar=asdf&amp;xxx=yyy'}
          test2:
            mock:
              - {title: 'Test', url: 'http://localhost/foo?bar=asdf&amp;xxx=yyy'}
            urlfix: no
    """

    def test_urlfix(self, execute_task):
        task = execute_task('test')
        entry = task.find_entry('entries', title='Test')
        assert entry['url'] == 'http://localhost/foo?bar=asdf&xxx=yyy', (
            'failed to auto fix url, got {}'.format(entry['url'])
        )

    def test_urlfix_disabled(self, execute_task):
        task = execute_task('test2')
        entry = task.find_entry('entries', title='Test')
        assert entry['url'] != 'http://localhost/foo?bar=asdf&xxx=yyy', (
            'fixed even when disabled, got {}'.format(entry['url'])
        )
