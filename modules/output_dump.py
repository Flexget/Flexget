import yaml

__pychecker__ = 'unusednames=parser'

class YamlDump:

    """
        Dummy module for testing, outputs all entries in yaml
    """

    def register(self, manager, parser):
        manager.register(event="output", keyword="dump", callback=self.dump, builtin=False, debug_module=True)

    def dump(self, feed):
        for entry in feed.entries:
            c = entry.copy()
            feed.manager.sanitize(c)
            print yaml.safe_dump(c)
