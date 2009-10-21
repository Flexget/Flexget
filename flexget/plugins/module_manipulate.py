import logging
import re
from flexget.plugin import *

log = logging.getLogger('manipulate')

class Manipulate:
    """
        Usage:
        
        manipulate:
          <field>:
            from: <field>
            regexp: ...
    """
    def validator(self):
        from flexget import validator
        root = validator.factory('dict')
        edit = root.accept_any_key('dict')
        edit.accept('text', key='from')
        edit.accept('regexp', key='regexp')
        return root

    def on_feed_filter(self, feed):
        for entry in feed.entries:
            for field, config in feed.config['manipulate'].iteritems():
                if not config['from'] in entry:
                    break
                match = re.match(config['regexp'], entry[config['from']])
                if match:
                    entry[field] = ' '.join(match.groups())
                    feed.verbose_details('field %s is now %s' % (field, entry[field]))
                    log.debug('field %s is now %s' % (field, entry[field]))

register_plugin(Manipulate, 'manipulate', priorities={filter: 255})