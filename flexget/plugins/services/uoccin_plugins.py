from __future__ import unicode_literals, division, absolute_import
from datetime import datetime
import logging
import os
import re
import shutil

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
        for eid, itm in section.items():
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
                    for sno in slist.keys():
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
                    for sno in slist.keys():
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


class UoccinLookup(object):

    schema = { 'type': 'string', 'format': 'path' }
    
    # Run after metainfo_series / thetvdb_lookup / imdb_lookup
    @plugin.priority(100)
    def on_task_metainfo(self, task, config):
        """Retrieves all the information found in the uoccin.json file for the entries.
        
        Example::
            
            uoccin_lookup: /path/to/gdrive/uoccin
        
        Resulting fields on entries:
        
        on series (requires tvdb_id):
        - uoccin_watchlist (true|false)
        - uoccin_rating (integer)
        - uoccin_tags (list)
        
        on episodes (requires tvdb_id, series_season and series_episode):
        - uoccin_collected (true|false)
        - uoccin_watched (true|false)
        - uoccin_subtitles (list of language codes)
        (plus the 3 series specific fields)
        
        on movies (requires imdb_id):
        - uoccin_watchlist (true|false)
        - uoccin_collected (true|false)
        - uoccin_watched (true|false)
        - uoccin_rating (integer)
        - uoccin_tags (list)
        - uoccin_subtitles (list of language codes)
        
        """
        if not task.entries:
            return
        udata = load_uoccin_data(config)
        movies = udata['movies']
        series = udata['series']
        for entry in task.entries:
            entry['uoccin_watchlist'] = False
            entry['uoccin_collected'] = False
            entry['uoccin_watched'] = False
            entry['uoccin_rating'] = None
            entry['uoccin_tags'] = []
            entry['uoccin_subtitles'] = []
            if 'tvdb_id' in entry:
                ser = series.get(str(entry['tvdb_id']))
                if ser is None:
                    continue
                entry['uoccin_watchlist'] = ser.get('watchlist', False)
                entry['uoccin_rating'] = ser.get('rating')
                entry['uoccin_tags'] = ser.get('tags', [])
                if all(field in entry for field in ['series_season', 'series_episode']):
                    season = str(entry['series_season'])
                    episode = entry['series_episode']
                    edata = ser.get('collected', {}).get(season, {}).get(str(episode))
                    entry['uoccin_collected'] = isinstance(edata, list)
                    entry['uoccin_subtitles'] = edata if entry['uoccin_collected'] else []
                    entry['uoccin_watched'] = episode in ser.get('watched', {}).get(season, [])
            elif 'imdb_id' in entry:
                mov = movies.get(entry['imdb_id'])
                if mov is None:
                    continue
                entry['uoccin_watchlist'] = mov.get('watchlist', False)
                entry['uoccin_collected'] = mov.get('collected', False)
                entry['uoccin_watched'] = mov.get('watched', False)
                entry['uoccin_rating'] = mov.get('rating')
                entry['uoccin_tags'] = mov.get('tags', [])
                entry['uoccin_subtitles'] = mov.get('subtitles', [])


class UoccinProcess(object):
    """Update the uoccin.json file applying one or more logged changes loaded from one or more uoccin diff files.
    A diff file is a text file. Each line represent a modification in this form:
      time|type|target|field|value
    where:
    - time is when the action took place. we'll sort the lines loaded from all the diff files prior to process them.
    - type must be 'movie' or 'series'.
    - target can be the movie imdb_id, the series tvdb_id or the episode id (in the form tvdb_id.season.episode,
      i.e. "230435.2.14").
    - field can be one of: watchlist, collected, watched, rating, tags, subtitles.
    - value can be:
      - true|false when field is watchlist, collected or watched.
      - a integer 0-n for rating (5 is the cap in the Android app).
      - a comma separated list for tags and subtitles.
    examples:
      1431093328971|movie|tt346578|watchlist|true
      1431093328995|movie|tt283759|collected|false
      1431093329029|series|80379|watchlist|true
      1431093329033|series|80379|tags|pippo,pluto
      1431175098984|series|80379.8.24|watched|true
      1431198108547|series|272135.2.5|collected|true
      1431198108565|series|272135.2.5|subtitles|eng,ita
    """
    
    def __init__(self):
        self.reset(None)
    
    def reset(self, folder):
        self.log = logging.getLogger('uoccin_process')
        self.folder = folder
        self.changes = []
    
    def load(self, filename):
        with open(filename, 'r') as f:
            lines = f.read().splitlines()
        if lines:
            self.log.info('found %d changes in %s' % (len(lines), filename))
            self.changes.extend(lines)
        else:
            self.log.debug('no changes found in %s' % filename)
    
    def process(self):
        imdb_lookup = plugin.get_plugin_by_name('imdb_lookup').instance
        self.changes.sort()
        udata = load_uoccin_data(self.folder)
        for line in self.changes:
            tmp = line.split('|')
            typ = tmp[1]
            tid = tmp[2]
            fld = tmp[3]
            val = tmp[4]
            self.log.verbose('processing: type=%s, target=%s, field=%s, value=%s' % (typ, tid, fld, val))
            if typ == 'movie':
                # default
                mov = udata['movies'].setdefault(tid, 
                    {'name':'N/A', 'watchlist':False, 'collected':False, 'watched':False})
                # movie title is unknown at this time
                fake = Entry()
                fake['url'] = 'http://www.imdb.com/title/' + tid
                fake['imdb_id'] = tid
                try:
                    imdb_lookup.lookup(fake)
                    mov['name'] = fake.get('imdb_name')
                except plugin.PluginError:
                    self.log.warning('Unable to lookup movie %s from imdb, using raw name.' % tid)
                # setting
                if fld == 'watchlist':
                    mov['watchlist'] = val == 'true'
                elif fld == 'collected':
                    mov['collected'] = val == 'true'
                elif fld == 'watched':
                    mov['watched'] = val == 'true'
                elif fld == 'tags':
                    mov['tags'] = re.split(',\s*', val)
                elif fld == 'subtitles':
                    mov['subtitles'] = re.split(',\s*', val)
                elif fld == 'rating':
                    mov['rating'] = int(val)
                # cleaning
                if not (mov['watchlist'] or mov['collected'] or mov['watched']):
                    self.log.verbose('deleting unused section: movies\%s' % tid)
                    udata['movies'].pop(tid)
            elif typ == 'series':
                tmp = tid.split('.')
                sid = tmp[0]
                sno = tmp[1] if len(tmp) > 2 else None
                eno = tmp[2] if len(tmp) > 2 else None
                # default
                ser = udata['series'].setdefault(sid, {'name':'N/A', 'watchlist':False, 'collected':{}, 'watched':{}})
                # series name is unknown at this time
                try:
                    series = lookup_series(tvdb_id=sid)
                    ser['name'] = series.seriesname
                except LookupError:
                    self.log.warning('Unable to lookup series %s from tvdb, using raw name.' % sid)
                # setting
                if fld == 'watchlist':
                    ser['watchlist'] = val == 'true'
                elif fld == 'tags':
                    ser['tags'] = re.split(',\s*', val)
                elif fld == 'rating':
                    ser['rating'] = int(val)
                elif sno is None or eno is None:
                    self.log.warning('invalid line "%s": season and episode numbers are required' % line)
                elif fld == 'collected':
                    season = ser['collected'].setdefault(sno, {})
                    if val == 'true':
                        season.setdefault(eno, [])
                    elif eno in season:
                        season.pop(eno)
                        if not season:
                            self.log.verbose('deleting unused section: series\%s\collected\%s' % (sid, sno))
                            ser['collected'].pop(sno)
                elif fld == 'subtitles':
                    ser['collected'].setdefault(sno, {})[eno] = re.split(',\s*', val)
                elif fld == 'watched':
                    season = ser['watched'].setdefault(sno, [])
                    if val == 'true':
                        season = ser['watched'][sno] = list(set(season) | set([int(eno)]))
                    elif eno in season:
                        season.remove(int(eno))
                    season.sort()
                    if not season:
                        self.log.debug('deleting unused section: series\%s\watched\%s' % (sid, sno))
                        ser['watched'].pop(sno)
                # cleaning
                if not (ser['watchlist'] or ser['collected'] or ser['watched']):
                    self.log.debug('deleting unused section: series\%s' % sid)
                    udata['series'].pop(sid)
            else:
                self.log.warning('invalid element type "%s"' % typ)
        # save the updated uoccin.json
        ufile = os.path.join(self.folder, 'uoccin.json')
        try:
            text = json.dumps(udata, sort_keys=True, indent=4, separators=(',', ': '))
            with open(ufile, 'w') as f:
                f.write(text)
        except Exception as err:
            self.log.debug('error writing %s: %s' % (ufile, err))
            raise plugin.PluginError('error writing %s: %s' % (ufile, err))


class UoccinReader(object):
    
    schema = {
        'type': 'object',
        'properties': {
            'uuid': {'type': 'string'},
            'path': {'type': 'string', 'format': 'path'},
        },
        'required': ['uuid', 'path'],
        'additionalProperties': False
    }
    
    processor = UoccinProcess()
    
    def on_task_start(self, task, config):
        UoccinReader.processor.reset(config['path'])
    
    def on_task_exit(self, task, config):
        UoccinReader.processor.process()
    
    def on_task_output(self, task, config):
        """Process incoming diff to update the uoccin.json file. Requires the location field.
        
        Example::
        
          uoccin_sync_task:
            seen: local
            find:
              path:
                - '{{ secrets.uoccin.path }}\device.{{ secrets.uoccin.uuid }}'
              regexp: '.*\.diff$'
            accept_all: yes
            uoccin_reader:
              uuid: '{{ secrets.uoccin.uuid }}'
              path: '{{ secrets.uoccin.path }}'
        
        Note::
        - the uoccin.json file will be created if not exists.
        - the uuid must be a filename-safe text.
        """
        for entry in task.accepted:
            if entry.get('location'):
                fn = os.path.basename(entry['location'])
                if fn.endswith('.diff') and not (config['uuid'] in fn):
                    UoccinReader.processor.load(entry['location'])
                    os.remove(entry['location'])
                else:
                    self.log.debug('skipping %s (not a foreign diff file)' % fn)


class UoccinWriter(object):
    
    out_queue = ''
    
    def on_task_start(self, task, config):
        # create the local device folder if not exists
        my_folder = os.path.join(config['path'], 'device.' + config['uuid'])
        if not os.path.exists(my_folder):
            os.makedirs(my_folder)
        # define the filename for the outgoing diff file
        ts = int((datetime.utcnow() - datetime(1970, 1, 1)).total_seconds() * 1000)
        fn = '%d.%s.diff' % (ts, config['uuid'])
        UoccinWriter.out_queue = os.path.join(my_folder, fn)
    
    def on_task_exit(self, task, config):
        if os.path.exists(UoccinWriter.out_queue):
            # update uoccin.json
            up = UoccinProcess()
            up.reset(config['path'])
            up.load(UoccinWriter.out_queue)
            up.process()
            # copy the diff file in other devices folders
            for fld in next(os.walk(config['path']))[1]:
                if fld.startswith('device.') and fld != ('device.' + config['uuid']):
                    shutil.copy2(UoccinWriter.out_queue, os.path.join(config['path'], fld))
                    self.log.verbose('%s copied in %s' % (UoccinWriter.out_queue, fld))
            # delete the diff file in the local device folder
            os.remove(UoccinWriter.out_queue)
    
    def append_command(self, target, title, field, value):
        ts = int((datetime.utcnow() - datetime(1970, 1, 1)).total_seconds() * 1000)
        line = '%d|%s|%s|%s|%s\n' % (ts, target, title, field, value)
        with open(UoccinWriter.out_queue, 'a') as f:
            f.write(line)


class UoccinWatchlist(UoccinWriter):
    
    # Defined by subclasses
    set_true = None
    
    def on_task_output(self, task, config):
        """Add or remove in the uoccin.json file watchlist the accepted series and/or movies.
        Requires tvdb_id for series and imdb_id for movies.
        
        Examples::
            
            uoccin_watchlist_add:
              uuid: flexget_server_home
              path: /path/to/gdrive/uoccin
              tags: [ 'discovered', 'evaluate', 'bazinga' ]
            
            uoccin_watchlist_remove:
              uuid: flexget_server_home
              path: /path/to/gdrive/uoccin
        
        Note::
        - the uoccin.json file will be created if not exists.
        - the uuid must be a filename-safe text.
        - for uoccin_watchlist_add at least 1 tag is required.
        """
        for entry in task.accepted:
            tid = None
            typ = None
            if entry.get('tvdb_id'):
                tid = entry['tvdb_id']
                typ = 'series'
            elif entry.get('imdb_id'):
                tid = entry['imdb_id']
                typ = 'movie'
            if tid is None:
                continue
            self.append_command(typ, tid, 'watchlist', str(self.set_true).lower())
            if self.set_true:
                self.append_command(typ, tid, 'tags', ",".join(config['tags']))


class UoccinWlstAdd(UoccinWatchlist):
    """Add all accepted series/movies to Uoccin watchlist."""
    schema = {
        'type': 'object',
        'properties': {
            'uuid': {'type': 'string'},
            'path': {'type': 'string', 'format': 'path'},
            'tags': {'type': 'array', 'items': {'type': 'string'}, 'minItems': 1},
        },
        'required': ['uuid', 'path'],
        'additionalProperties': False
    }
    set_true = True


class UoccinWlstDel(UoccinWatchlist):
    """Remove all accepted elements from Uoccin watchlist."""
    schema = {
        'type': 'object',
        'properties': {
            'uuid': {'type': 'string'},
            'path': {'type': 'string', 'format': 'path'},
        },
        'required': ['uuid', 'path'],
        'additionalProperties': False
    }
    set_true = False


class UoccinCollection(UoccinWriter):

    schema = {
        'type': 'object',
        'properties': {
            'uuid': {'type': 'string'},
            'path': {'type': 'string', 'format': 'path'},
        },
        'required': ['uuid', 'path'],
        'additionalProperties': False
    }
    
    # Defined by subclasses
    set_true = None
    
    def on_task_output(self, task, config):
        """Set the accepted episodes and/or movies as collected (or not) in the uoccin.json file.
        Requires tvdb_id, series_season and series_episode fields for episodes, or imdb_id for movies.
        
        Example::
            
            uoccin_collection_remove:
              uuid: flexget_server_home
              path: /path/to/gdrive/uoccin
        
        Note::
        - the uoccin.json file will be created if not exists.
        - the uuid must be a filename-safe text.
        """
        for entry in task.accepted:
            tid = None
            typ = None
            if all(field in entry for field in ['tvdb_id', 'series_season', 'series_episode']):
                tid = '%s.%d.%d' % (entry['tvdb_id'], entry['series_season'], entry['series_episode'])
                typ = 'series'
            elif entry.get('imdb_id'):
                tid = entry['imdb_id']
                typ = 'movie'
            if tid is None:
                continue
            self.append_command(typ, tid, 'collected', str(self.set_true).lower())
            if self.set_true and 'subtitles' in entry:
                self.append_command(typ, tid, 'subtitles', ",".join(entry['subtitles']))


class UoccinCollAdd(UoccinCollection):
    """Add/update all accepted elements in uoccin collection."""
    set_true = True


class UoccinCollDel(UoccinCollection):
    """Remove all accepted elements from uoccin collection."""
    set_true = False


class UoccinWatched(UoccinWriter):

    schema = {
        'type': 'object',
        'properties': {
            'uuid': {'type': 'string'},
            'path': {'type': 'string', 'format': 'path'},
        },
        'required': ['uuid', 'path'],
        'additionalProperties': False
    }
    
    # Defined by subclasses
    set_true = None
    
    def on_task_output(self, task, config):
        """Set the accepted episodes and/or movies as watched (or not) in the uoccin.json file.
        Requires tvdb_id, series_season and series_episode fields for episodes, or imdb_id for movies.
        
        Example::
            
            uoccin_watched_true:
              uuid: flexget_server_home
              path: /path/to/gdrive/uoccin
        
        Note::
        - the uoccin.json file will be created if not exists.
        - the uuid must be a filename-safe text.
        """
        for entry in task.accepted:
            tid = None
            typ = None
            if all(field in entry for field in ['tvdb_id', 'series_season', 'series_episode']):
                tid = '%s.%d.%d' % (entry['tvdb_id'], entry['series_season'], entry['series_episode'])
                typ = 'series'
            elif entry.get('imdb_id'):
                tid = entry['imdb_id']
                typ = 'movie'
            if tid is None:
                continue
            self.append_command(typ, tid, 'watched', str(self.set_true).lower())


class UoccinSeenAdd(UoccinWatched):
    """Set all accepted elements as watched."""
    set_true = True


class UoccinSeenDel(UoccinWatched):
    """Set all accepted elements as not watched."""
    set_true = False


class UoccinSubtitles(UoccinWriter):

    schema = {
        'type': 'object',
        'properties': {
            'uuid': {'type': 'string'},
            'path': {'type': 'string', 'format': 'path'},
        },
        'required': ['uuid', 'path'],
        'additionalProperties': False
    }
    
    def on_task_output(self, task, config):
        """Set subtitles info for accepted episodes and/or movies in the uoccin.json file.
        Requires the subtitles field (set by subtitles_check plugin), plus tvdb_id, series_season and series_episode 
        for episodes, or imdb_id for movies.
        
        Example::
            
            uoccin_subtitles:
              uuid: flexget_server_home
              path: /path/to/gdrive/uoccin
        
        Note::
        - the uoccin.json file will be created if not exists.
        - the uuid must be a filename-safe text.
        """
        for entry in task.accepted:
            if not entry.get('subtitles'):
                continue
            tid = None
            typ = None
            if all(field in entry for field in ['tvdb_id', 'series_season', 'series_episode']):
                tid = '%s.%d.%d' % (entry['tvdb_id'], entry['series_season'], entry['series_episode'])
                typ = 'series'
            elif entry.get('imdb_id'):
                tid = entry['imdb_id']
                typ = 'movie'
            if tid is None:
                continue
            self.append_command(typ, tid, 'subtitles', ",".join(entry['subtitles']))


@event('plugin.register')
def register_plugin():
    plugin.register(UoccinEmit, 'uoccin_emit', api_ver=2)
    plugin.register(UoccinLookup, 'uoccin_lookup', api_ver=2)
    plugin.register(UoccinReader, 'uoccin_reader', api_ver=2)
    plugin.register(UoccinWlstAdd, 'uoccin_watchlist_add', api_ver=2)
    plugin.register(UoccinWlstDel, 'uoccin_watchlist_remove', api_ver=2)
    plugin.register(UoccinCollAdd, 'uoccin_collection_add', api_ver=2)
    plugin.register(UoccinCollDel, 'uoccin_collection_remove', api_ver=2)
    plugin.register(UoccinSeenAdd, 'uoccin_watched_true', api_ver=2)
    plugin.register(UoccinSeenDel, 'uoccin_watched_false', api_ver=2)
    plugin.register(UoccinSubtitles, 'uoccin_subtitles', api_ver=2)
