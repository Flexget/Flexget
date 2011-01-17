import urlparse
import logging
from flexget.feed import Entry
from flexget.plugin import *

log = logging.getLogger('imdb_queue_input')


class InputIMDBQueue(object):
    """
    Get a list of titles from the IMDB queue
    """

    def validator(self):
        from flexget import validator
        return validator.factory('boolean')
    
    def on_feed_input(self, feed):
        if feed.config.get("imdb_queue_input"):
            try:
                imdb_entries = get_plugin_by_name('imdb_queue_manager')\
                       .instance.queue_get(feed.session)
            except PluginError:
                # no IMDB data, can't do anything
                log.error("Could not get imdb_queue_manager instance")
            for imdb_entry in imdb_entries:
                entry = Entry()
                # make sure the entry has IMDB fields filled
                entry['imdb_url'] = 'http://www.imdb.com/title/' + imdb_entry[1]
                entry['imdb_id'] = imdb_entry[1]
                if imdb_entry[0][:26] != "http://www.imdb.com/title/":
                    entry['title'] = imdb_entry[0]
                else:
                    try:
                        get_plugin_by_name('imdb_lookup').instance.lookup(feed, 
                                                                          entry)
                    except PluginError:
                        log.error("Found imdb url in imdb queue, "\
                                  "but lookup failed: %s" % entry['imdb_url'])
                        continue
                    entry['title'] = entry['imdb_name']
                entry['url'] = ''
                feed.entries.append(entry)
                log.debug("Added title and IMDB id to new entry: %s - %s" % 
                         (entry['title'], entry['imdb_id']))
        return

register_plugin(InputIMDBQueue, 'imdb_queue_input')
