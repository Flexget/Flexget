"""
    Provides some classes that are usefull when developing new modules.
"""

class MockOptions:

    nocache = False
    
class MockManager:
    def __init__(self):
        self.options = MockOptions()

class MockCache:
    def store(self, key, value, days=30):
        pass

    def get(self, key, default=None):
        return None
    

class MockFeed:
    def __init__(self):
        self.config = {}
        self.entries = []
        self.name = "Mock"
        self.manager = MockManager()
        self.cache = MockCache()
        self.shared_cache = MockCache()

    def get_input_url(self, name):
        import sys
        if len(sys.argv) > 0:
            return sys.argv[1]
        else:
            return "http://127.0.0.1/test"

    def filter(self, entry):
        print "MockFeed got filtering command on %s" % entry['title']

    def dump_entries(self):
        # available only in mock!
        import yaml
        for entry in self.entries:
            c = entry.copy()
            if c.has_key('data'):
                c['data'] = '<%i bytes of data>' % len(c['data'])
            if c.has_key('torrent'):
                c['torrent'] = '<torrent object>'
            print yaml.safe_dump(c)
        
