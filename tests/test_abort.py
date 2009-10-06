from tests import FlexGetBase

class TestAbort(FlexGetBase):
    
    __yaml__ = """
        feeds:
          test:
            input_mock:
              - {title: 'Abort'}
            interval: 10 days # causes abort
    """
    
    def testAbort(self):
        self.execute_feed('test')
        assert self.feed._abort, 'Feed not aborted'