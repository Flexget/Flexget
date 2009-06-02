import logging

log = logging.getLogger('dump_config')

class OutputDumpConfig:

    """
        Dumps feed config in STDOUT in yaml at exit or abort event.
    """

    def register(self, manager, parser):
        manager.register('dump_config', debug_module=True)
        
    def validator(self, config):
        from flexget import validator
        return validator.factory('boolean')

    def feed_exit(self, feed):
        import yaml
        print '--- %s' % feed.name
        print yaml.safe_dump(feed.config)
        print '---'
        
    feed_abort = feed_exit
