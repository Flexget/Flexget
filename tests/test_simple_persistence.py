from flexget.utils.simple_persistence import SimplePersistence


class TestSimplePersistence:
    config = """
        tasks:
          test:
            mock:
              - {title: 'irrelevant'}
    """

    def test_setdefault(self, execute_task):
        task = execute_task('test')

        value1 = task.simple_persistence.setdefault('test', 'abc')
        value2 = task.simple_persistence.setdefault('test', 'def')

        assert value1 == value2, 'set default broken'

    def test_nosession(self, execute_task):
        persist = SimplePersistence('testplugin')
        persist['aoeu'] = 'test'
        assert persist['aoeu'] == 'test'
        # Make sure it commits and actually persists
        persist = SimplePersistence('testplugin')
        assert persist['aoeu'] == 'test'
