"""
    Provides some classes that are usefull when developing new modules.
"""

import yaml

class MockOptions:
    nocache = False
    
class MockManager:
    def __init__(self):
        self.options = MockOptions()

class MockCache:
    def store(self, key, value, days=30):
        print "store key: %s value: %s" % (key, yaml.safe_dump(value))

    def storedefault(self, key, value, default, days=30):
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
        """Available only in mock! Dumps entries in yaml"""
        for entry in self.entries:
            c = entry.copy()
            if c.has_key('data'):
                c['data'] = '<%i bytes of data>' % len(c['data'])
            if c.has_key('torrent'):
                c['torrent'] = '<torrent object>'
            print yaml.safe_dump(c)
        

def test_resolver(resolver):
    """Simple method to test a instance of resolver. Used when debugging them from command line"""
    import sys
    feed = MockFeed()

    mock = {}
    mock['title'] = 'mock'
    mock['url'] = sys.argv[1]

    solvable = resolver.resolvable(feed, mock)
    print "Resolvable : %s" % solvable
    if solvable:
        old = mock['url']
        success = resolver.resolve(feed, mock)
        print "Resolved   : %s -> %s" % (old, mock['url'])
        print "Succeeded  : %s" % success
    