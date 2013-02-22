# TODO:
# Store time of last downloaded movie 
#   - (if time of this run >= time of last download + TIMEFRAME) -> accept entry in task
#   - must be done after _all_ filters are done and all the tasks have run
# Implement configs (find docs on flexget site)
# Done?

# OPTIONS: (IDEAS)
# timeframe: weekly (daily|weekly|monthly)
# sort_by: rating (rating|votes|new(?))
# secondary: votes (votes|rating|new) 


import logging
from datetime import datetime, timedelta
from flexget.plugin import register_plugin, get_plugin_by_name, PluginError, priority
from flexget.utils.log import log_once
from flexget import schema
from flexget.manager import Session
from flexget.entry import Entry
from sqlalchemy import Column, Integer, DateTime, Unicode, Index, Float

log = logging.getLogger('get_best_seen')

SCHEMA_VER = 0

Base = schema.versioned_base('best_seen', SCHEMA_VER)

@schema.upgrade('best_seen')
def upgrade(ver, session):
	"""Putting this here so it's ready"""
	return ver

class BestSeen(Base):
	__tablename__ = 'best_seen'
	id = Column(Integer, primary_key=True)
	title = Column(Unicode, index=True)
	url = Column(Unicode, index=True)
	imdb_id = Column(Unicode, index=True)
	imdb_rating = Column(Float, index=True)
	imdb_votes = Column(Integer)
	added = Column(DateTime, index=True)
	last_download = Column(DateTime)

	def __init__(self):
		self.added = datetime.now()

	def __str__(self):
		return '<BestSeen(title=%s,url=%s,imdb_rating=%s,imdb_votes=%s,added=%s,last_download=%s)>' %\
						(self.title, self.url, str(self.imdb_rating), str(self.imdb_votes), 
							self.added.strftime('%Y-%m-%d %H:%M'), self.last_download.strftime('%Y-%m-%d %H-%M'))


class GetBest(object):
	"""
	This is a plugin for the imdb plugin

	It enables you to specify a number of days to wait,
	and if no entries have been accepted within that time,
	it will accept the highest ranking entry it has seen.

	Configuration:
		get_best_seen:
		  timeframe: <int≥

	# to wait for a week:
	get_best_seen:
	  timeframe: 7

	"""
	def validator(self):
		"""Validate configuration"""
		from flexget import validator
		getbest = validator.factory('dict')
		getbest.accept('integer', key='timeframe')
		return getbest

	@priority(110)
	def on_task_filter(self, task, config):
		
		""" Getting the entry in the database """
		item = task.session.query(BestSeen).first()
		
		

		try:
			val0 = item.imdb_rating
		except AttributeError:
			val0 = 0

		""" If last accepted entry was more than timeframe days ago """
		""" Accept the entry in the database. This will also cause the database to clean itself """
		if item:
			delta = item.last_download + timedelta(days=config['timeframe'])

			if (datetime.now() > delta):	
				args = {'title':item.title, 'url':item.url}
				entry = Entry(**args)
				entry.task = task
				entry.update('imdb_id',item.imdb_id)
				task.all_entries.append(entry)
				reason = 'Timeframe exceeded, accepting entry.'
				entry.accept(reason)

		
		if (len(task.accepted) == 0):
			""" Find the highest rated in this run """
			highest_entry = Entry()
			for entry in task.undecided:
				try: 
					val1 = highest_entry['imdb_score']
				except KeyError:
					val1 = 0

				try: 
					val2 = entry['imdb_score']
				except:
					val2 = 0

				if (val1 <= val2):
					highest_entry = entry

			""" If this entry has a higher imdb_score than the one stored, store this one instead """
			if val0 < highest_entry['imdb_score']:	
				if item:
					last_download = item.last_download
					task.session.delete(item)
				else:
					last_download = datetime.now()
				rp = BestSeen()
				rp.title = highest_entry['title']
				rp.url = highest_entry['url']
				rp.last_download = last_download
				try:
					rp.imdb_id = highest_entry['imdb_id']
				except KeyError:
					log.debug('IMDB ID could not be found for movie %s, discarding entry' % (entry['title']))
				try:
					rp.imdb_rating = highest_entry['imdb_score']
				except KeyError:
					log.debug('IMDB score could not be found for movie %s, discarding entry' % (entry['title']))
				try:
					rp.imdb_votes = highest_entry['imdb_votes']
				except KeyError:
					log.debug('IMDB votes could not be found for movie %s, discarding entry' % (entry['title']))
				task.session.add(rp)

		# """ If there was any accepted entries in the task, making sure it will be overwritten next run """
		else:
			if item:
				task.session.delete(item)
			rp = BestSeen()
			rp.last_download = datetime.now()
			rp.imdb_rating = 0
			task.session.add(rp)
			log.verbose('Found accepted entries - adding NULL object to best seen, starting over.')


register_plugin(GetBest, 'get_best_seen', api_ver=2)