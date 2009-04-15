import yaml

__pychecker__ = 'unusednames=parser'

class YamlDump:

    """
        Dummy plugin for testing, outputs all entries in yaml
    """

    def register(self, manager, parser):
        manager.register('dump', debug_plugin=True)
        
    def validator(self):
        import validator
        return validator.factory('any')

    def feed_output(self, feed):
        for entry in feed.accepted:
            c = entry.copy()
            feed.manager.sanitize(c)
            print yaml.safe_dump(c)
