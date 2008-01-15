

class TestFilter:

    def register(self, manager, parser):
        manager.register(instance=self, type="filter", keyword="testfilter", callback=self.run, order=999, debug_module=True)

    def run(self, feed):
        for entry in feed.entries:
            print "filter test: %s" % (entry)
