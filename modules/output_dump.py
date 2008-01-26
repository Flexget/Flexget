import yaml

class YamlDump:

    """
        Dummy module for testing, outputs all entries in yaml
    """

    def register(self, manager, parser):
        manager.register(instance=self, event="output", keyword="dump", callback=self.dump, builtin=False, debug_module=True)

    def dump(self, feed):
        for entry in feed.entries:
            c = entry.copy()
            if c.has_key('data'):
                c['data'] = '<%i bytes of data>' % len(c['data'])
            print yaml.safe_dump(c)
