import logging
from datetime import datetime, timedelta
from flexget.plugin import register_plugin, get_plugin_by_name, PluginError, priority
from flexget.utils.log import log_once
from flexget import schema
from flexget.manager import Session
from flexget.entry import Entry
from sqlalchemy import Column, Integer, DateTime, Unicode, Index, Float, desc
from flexget.utils.tools import parse_timedelta
from flexget.utils.qualities import Quality
from operator import attrgetter
from heapq import heapify, heapreplace

log = logging.getLogger('get_best_seen')

SCHEMA_VER = 0

Base = schema.versioned_base('best_seen', SCHEMA_VER)
Expires = schema.versioned_base('best_seen_expires', SCHEMA_VER)


@schema.upgrade('best_seen')
def upgrade(ver, session):
    # Putting this here so it's ready
    return ver


class BestSeen(Base):
    __tablename__ = 'best_seen'
    id = Column(Integer, primary_key=True)
    title = Column(Unicode, index=True)
    url = Column(Unicode, index=True)
    entry_id = Column(Unicode)
    sort_by = Column(Unicode)
    quality = Column(Unicode)
    rating = Column(Float, index=True)
    added = Column(DateTime, index=True)

    def __init__(self):
        self.added = datetime.now()
        self.last_download = datetime.now()

    def __str__(self):
        return '<BestSeen(title=%s, url=%s, entry_id=%s, rating=%s, added=%s, quality=%s, sort_by=%s)>' %\
            (self.title, self.url, self.entry_id, self.rating, 
                self.added.strftime('%Y-%m-%d %H:%M'), self.quality, self.sort_by)


class BestSeenExpires(Expires):
    __tablename__ = 'best_seen_expires'
    expires = Column(DateTime, primary_key=True)
    timeframe = Column(Unicode)

    def __init__(self):
        self.expires = datetime.now()

    def __str__(self):
        return '<BestSeenExpires(expires=%s, timeframe=%s)>' % (self.expires.strftime('%Y-%m-%d %H:%M'), self.timeframe)


class GetBest(object):
    """
    This plugin will look for entries as long as there are no accepted entries.

    Requires imdb_lookup or rottentomatoes_lookup, either specifically or
    implicitly (i.e by using imdb or rottentomatoes)

    It enables you to specify a number of days to wait,
    and if no entries have been accepted within that time,
    it will accept the highest ranking entry it has seen.

    Plugin will also pick the entry with the highest quality,
    if the same movie is available in different quality.

    Dependencies: Either imdb_lookup or rottentomatoes_lookup

    Configuration:
        get_best_seen:
            timeframe: [your preferred timeframe]
            number: <int>
            by: <what to sort by> (imdb_score, rt_average_score, ie. Must be sortable)

    # to get best 2 movies every week, judged from imdb_score:
    get_best_seen:
        timeframe: 7 days
        number: 2 
        by: imdb_score 

    possible values for 'by':

    - imdb_score
    - rt_average_score
    - rt_critics_rating
    - rt_critics_score
    - rt_audience_rating
    - rt_audience_score
    - rt_average_score

    

    """
    def validator(self):
        # Validate configuration
        from flexget import validator
        getbest = validator.factory('dict')
        getbest.accept('text', key='timeframe')
        getbest.accept('integer', key='number')
        getbest.accept('text', key='by')
        return getbest

    @priority(90)
    def on_task_filter(self, task, config):

        #  Set default config 
        if 'timeframe' not in config:
            config['timeframe'] = '7 days'
        if 'by' not in config:
            config['by'] = 'imdb_score'
        if 'number' not in config:
            config['number'] = 2

        #  Getting the entry in the database 
        items = task.session.query(BestSeen).order_by(desc(BestSeen.rating)).all()
        
        #  If timeframe has expired, accept entries, skip the rest 
        expire_time = task.session.query(BestSeenExpires).first()
        if not expire_time:
            expire_time = BestSeenExpires()
            expire_time.expires += parse_timedelta(config['timeframe'])
            expire_time.timeframe = config['timeframe']
            task.session.add(expire_time)
        else:
            if datetime.now() > expire_time.expires:
                self.accept_entries(config['by'], items, task)
            elif expire_time.timeframe != config['timeframe']:
                #  If timeframe has changed, update the timeframe, and check if it has expired 
                expire_time.timeframe = config['timeframe']
                task.session.add(expire_time)

        #  If the 'by' config item has changed, empty database 
        for item in items:
            if item.sort_by != config['by']:
                task.session.query(BestSeen).delete()
                items = []
                break

        #  Add enough empty items to the list 
        while len(items) < config['number']:
            items.append(BestSeen())

        #  Remove items if there are more in the database than specified in config (i.e config changed) 
        while len(items) > config['number']:
            item = items.pop()
            task.session.delete(item)

        heapify(items)
        
        if not task.accepted:
            for entry in task.undecided:
                #  Sort items descending, lowest will be last 
                
                entry_rating = entry.get(config['by'], 0)

                entry_title = entry.get('title')
                if config['by'].startswith('imdb'):
                    entry_id = entry.get('imdb_id')
                elif config['by'].startswith('rt'):
                    entry_id = entry.get('rt_id')
                else:
                    entry_id = None

                if self.exists(config['by'], entry_id, entry, items):
                    #  If this entry's movie id with this quality is already in database, move on 
                    continue

                for item in items:
                    
                    if entry_rating > item.rating:
                        new = BestSeen()
                        new.url = entry.get('url')
                        new.title = entry.get('title')
                        new.sort_by = config['by']
                        new.entry_id = entry_id
                        new.rating = entry_rating
                        new.quality = str(entry.get('quality', None))
                        new.added = datetime.now()
                        heapreplace(items, new)
                        items.sort(key=attrgetter('rating'))
                        break
                    elif entry_id == item.entry_id and self.entry_higher_q(entry, item):
                        #  Same movie, better quality, switch them 
                        new = BestSeen()
                        new.url = entry.get('url')
                        new.title = entry.get('title')
                        new.sort_by = config['by']
                        new.entry_id = entry_id
                        new.rating = entry_rating
                        new.quality = str(entry.get('quality', None))
                        new.added = datetime.now()
                        items.remove(item)
                        items.append(new)
                        items.sort(key=attrgetter('rating'))
                
            for item in items:
                #  Add items to database. Session takes care of dupes 
                task.session.add(item)
        else:
            # empty database, set time in other table
            now = BestSeenExpires()
            now.expires += parse_timedelta(config['timeframe'])
            now.timeframe = config['timeframe']
            before = task.session.query(BestSeenExpires).first()
            task.session.add(now)
            task.session.delete(before)
            #  Empty database 
            task.session.query(BestSeen).delete()

    # Checks if an item already exists in the database. 
    # Should also return false if the items id is identical, but quality differs 
    def exists(self, by, entry_id, entry, items):
        for item in items:
            if str(entry_id) == item.entry_id and not self.entry_higher_q(entry, item):
                return True
        return False

    def entry_higher_q(self, entry, item):
        entry_q = entry.get('quality')
        item_q = Quality(item.quality)
        return entry_q.__gt__(item_q)

    # Does all the accepting of entries 
    def accept_entries(self, by, items, task):
        for item in items:
            args = {'title': item.title, 'url': item.url}
            entry = Entry(**args)
            entry.task = task
            if by.startswith('imdb'):
                entry.update({'imdb_id': item.id})
            elif by.startswith('rt'):
                entry.update({'rt_id': item.id})
            task.all_entries.append(entry)
            reason = 'Timeframe exceeded, accepting entry.'
            entry.accept(reason)

register_plugin(GetBest, 'get_best_seen', api_ver=2)
