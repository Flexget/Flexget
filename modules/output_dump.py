import yaml

__pychecker__ = 'unusednames=parser'

class YamlDump:

    """
        Dummy module for testing, outputs all entries in yaml
    """

    def register(self, manager, parser):
        manager.register('dump', debug_module=True)

    def feed_output(self, feed):
        for entry in feed.entries:
            c = entry.copy()
            feed.manager.sanitize(c)
            print yaml.safe_dump(c)
