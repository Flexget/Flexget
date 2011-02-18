import logging
from flexget.feed import Entry
from flexget.plugin import register_plugin, PluginError, get_plugin_by_name

log = logging.getLogger('emit_imdb')


class EmitIMDBQueue(object):
    """
    Use your imdb queue as an input by emitting the content of it
    """

    def validator(self):
        from flexget import validator
        return validator.factory('boolean')

    def on_feed_input(self, feed):
        if not feed.config.get("emit_imdb_queue"):
            return

        imdb_entries = get_plugin_by_name('imdb_queue_manager').\
               instance.queue_get(feed.session)

        for imdb_entry in imdb_entries:
            entry = Entry()
            # make sure the entry has IMDB fields filled
            entry['imaginary'] = True
            entry['imdb_url'] = 'http://www.imdb.com/title/' + imdb_entry[1]
            entry['imdb_id'] = imdb_entry[1]
            if imdb_entry[0][:26] != "http://www.imdb.com/title/":
                entry['title'] = imdb_entry[0]
            else:
                try:
                    get_plugin_by_name('imdb_lookup').instance.\
                        lookup(feed, entry)
                except PluginError:
                    log.error("Found imdb url in imdb queue, "\
                              "but lookup failed: %s" % entry['imdb_url'])
                    continue
                entry['title'] = entry['imdb_name']
            entry['url'] = ''
            feed.entries.append(entry)
            log.debug("Added title and IMDB id to new entry: %s - %s" %
                     (entry['title'], entry['imdb_id']))

register_plugin(EmitIMDBQueue, 'emit_imdb_queue')
