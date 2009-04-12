import os
import logging
from manager import ModuleWarning

log = logging.getLogger('scan_imdb')

class ModuleScanImdb:

    """
        Scan entry information for imdb url
    """

    def register(self, manager, parser):
        manager.register('scan_imdb', filter_priority=200)

    def validator(self):
        import validator
        return validator.factory('boolean')

    def feed_filter(self, feed):
        pass
        
        # TODO: implement!
