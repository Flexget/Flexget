import logging

__pychecker__ = 'unusednames=parser'

log = logging.getLogger('dump_config')

class OutputDumpConfig:

    """
        Dumps feed config in STDOUT in yaml at exit event.
    """

    def register(self, manager, parser):
        manager.register('dump_config', debug_module=True)
        
    def validate(self, config):
        return []

    def feed_exit(self, feed):
        import yaml
        print '---'
        print yaml.safe_dump(feed.config)
        print '---'
