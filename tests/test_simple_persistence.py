from tests import FlexGetBase


class TestSimplePersistence(FlexGetBase):
    
    __yaml__ = """
        feeds:
          test:
            mock:
              - {title: 'irrelevant'}
    """
    
    def test_setdefault(self):
        self.execute_feed('test')

        feed = self.feed

        value1 = feed.simple_persistence.setdefault('test', 'abc')
        value2 = feed.simple_persistence.setdefault('test', 'def')

        assert value1 == value2, 'set default broken'
