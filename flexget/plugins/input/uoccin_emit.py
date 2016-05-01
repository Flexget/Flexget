from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import os

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils import json

try:
    from flexget.plugins.api_tvdb import lookup_series
except ImportError:
    raise plugin.DependencyError(issued_by='uoccin', missing='api_tvdb',
                                 message='uoccin requires the `api_tvdb` plugin')


def load_uoccin_data(path):
    udata = {}
    ufile = os.path.join(path, 'uoccin.json')
    if os.path.exists(ufile):
        try:
            with open(ufile, 'r') as f:
                udata = json.load(f)
        except Exception as err:
            raise plugin.PluginError('error reading %s: %s' % (ufile, err))
    udata.setdefault('movies', {})
    udata.setdefault('series', {})
    return udata


class UoccinEmit(object):

    schema = {
        'type': 'object',
        'properties': {
            'path': {'type': 'string', 'format': 'path'},
            'type': {'type': 'string', 'enum': ['movies', 'series', 'episodes']},
            'tags': {'type': 'array', 'items': {'type': 'string'}, 'minItems': 1},
            'check_tags': {'type': 'string', 'enum': ['any', 'all', 'none'], 'default': 'any'},
            'ep_flags': {'type': 'string', 'enum': ['watched', 'collected'], 'default': 'watched'},
        },
        'required': ['path', 'type'],
        'additionalProperties': False
    }
    
    def on_task_input(self, task, config):
        """Creates an entry for each item in your uoccin watchlist.
        
        Example::
            
            uoccin_emit:
              path: /path/to/gdrive/uoccin
              type: series
              tags: [ 'favorite', 'hires' ]
              check_tags: all
        
        Options path and type are required while the others are for filtering:
        - 'any' will include all the items marked with one or more tags in the list
        - 'all' will only include the items marked with all the listed tags
        - 'none' will only include the items not marked with any of the listed tags.
        
        The entries created will have a valid imdb/tvdb url and id.
        """
        imdb_lookup = plugin.get_plugin_by_name('imdb_lookup').instance
        udata = load_uoccin_data(config['path'])
        section = udata['movies'] if config['type'] == 'movies' else udata['series']
        entries = []
        for eid, itm in list(section.items()):
            if not itm['watchlist']:
                continue
            if 'tags' in config:
                n = len(set(config['tags']) & set(itm.get('tags', [])))
                if config['check_tags'] == 'any' and n <= 0:
                    continue
                if config['check_tags'] == 'all' and n != len(config['tags']):
                    continue
                if config['check_tags'] == 'none' and n > 0:
                    continue
            if config['type'] == 'movies':
                entry = Entry()
                entry['url'] = 'http://www.imdb.com/title/' + eid
                entry['imdb_id'] = eid
                if itm['name'] != 'N/A':
                    entry['title'] = itm['name']
                else:
                    try:
                        imdb_lookup.lookup(entry)
                    except plugin.PluginError as e:
                        self.log.trace('entry %s imdb failed (%s)' % (entry['imdb_id'], e.value))
                        continue
                    entry['title'] = entry.get('imdb_name')
                if 'tags' in itm:
                    entry['uoccin_tags'] = itm['tags']
                if entry.isvalid():
                    entries.append(entry)
                else:
                    self.log.debug('Invalid entry created? %s' % entry)
            else:
                sname = itm['name']
                try:
                    sname = lookup_series(tvdb_id=eid).seriesname
                except LookupError:
                    self.log.warning('Unable to lookup series %s from tvdb, using raw name.' % eid)
                surl = 'http://thetvdb.com/?tab=series&id=' + eid
                if config['type'] == 'series':
                    entry = Entry()
                    entry['url'] = surl
                    entry['title'] = sname
                    entry['tvdb_id'] = eid
                    if 'tags' in itm:
                        entry['uoccin_tags'] = itm['tags']
                    if entry.isvalid():
                        entries.append(entry)
                    else:
                        self.log.debug('Invalid entry created? %s' % entry)
                elif config['ep_flags'] == 'collected':
                    slist = itm.get('collected', {})
                    for sno in list(slist.keys()):
                        for eno in slist[sno]:
                            entry = Entry()
                            entry['url'] = surl
                            entry['title'] = '%s S%02dE%02d' % (sname, int(sno), int(eno))
                            entry['tvdb_id'] = eid
                            if entry.isvalid():
                                entries.append(entry)
                            else:
                                self.log.debug('Invalid entry created? %s' % entry)
                else:
                    slist = itm.get('watched', {})
                    for sno in list(slist.keys()):
                        for eno in slist[sno]:
                            entry = Entry()
                            entry['url'] = surl
                            entry['title'] = '%s S%02dE%02d' % (sname, int(sno), eno)
                            entry['tvdb_id'] = eid
                            if entry.isvalid():
                                entries.append(entry)
                            else:
                                self.log.debug('Invalid entry created? %s' % entry)
        entries.sort(key=lambda x: x['title'])
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(UoccinEmit, 'uoccin_emit', api_ver=2)
