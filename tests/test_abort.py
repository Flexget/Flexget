from tests import FlexGetBase

class TestAbort(FlexGetBase):
    
    __yaml__ = """
        feeds:
          test:
            # causes on_feed_abort to be called
            disable_builtins: yes 

            # causes abort
            interval: 10 days
            
            # another event hookup with this plugin
            headers:
              test: value 
    """
    
    def testAbort(self):
        self.execute_feed('test')
        assert self.feed._abort, 'Feed not aborted'