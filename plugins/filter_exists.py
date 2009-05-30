import os
import logging
from manager import PluginWarning
from utils.series import SeriesParser

log = logging.getLogger('exists')

class FilterExists:

    """
        Reject entries that already exist in given path.

        Example:

        exists: /storage/movies/
    """

    def register(self, manager, parser):
        manager.register('exists', filter_priority=-1)

    def validator(self):
        import validator
        root = validator.factory()
        root.accept('text')
        bundle = root.accept('list')
        bundle.accept('text')
        return root # TODO: path
        
    def get_config(self, feed):
        config = feed.config.get('exists', None)
        #if only a single path is passed turn it into a 1 element list
        if isinstance(config, str):
            config = [config]
        return config
                
          

    def feed_filter(self, feed):
        config = self.get_config(feed)
        for path in config:
            path = os.path.expanduser(path)
            if not os.path.exists(path):
                raise PluginWarning('Path %s does not exist' % path, log)
            # scan through
            for root, dirs, files in os.walk(path):
                # convert filelists into utf-8 to avoid unicode problems
                dirs = [x.decode('utf-8', 'ignore') for x in dirs]
                files = [x.decode('utf-8', 'ignore') for x in files]
                for entry in feed.entries:
                    name = entry['title']
                    if name in dirs or name in files:
                        log.debug('Found %s in %s' % (name, root))
                        feed.reject(entry, '%s/%s' % (name, root))
                    elif 'series_parser' in entry:
                        for afile in files:
                            #make new parser from parser in entry
                            parser = SeriesParser()
                            oldparser = entry['series_parser']
                            parser.name = oldparser.name
                            parser.ep_regexps = oldparser.ep_regexps
                            parser.id_regexps = oldparser.id_regexps
                            #run parser on filename data
                            parser.data = afile
                            parser.parse()
                            if parser.valid:
                                if parser.identifier()==oldparser.identifier() and parser.quality==oldparser.quality:
                                    log.debug('Found episode %s %s in %s' % (parser.name, parser.identifier(), root))
                                    feed.reject(entry, 'episode already exists')
                            
