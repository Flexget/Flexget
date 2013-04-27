import logging
from flexget import validator
from flexget.plugin import register_plugin
from flexget.plugins.filter.series import forget_series_episode
from flexget.plugins.filter import seen

log = logging.getLogger('series_forget')

class OutputSeriesForget(object):
	def validator(self):
		from flexget import validator
		root = validator.factory()
		root.accept('list').accept('choice').accept_choices(['seen','series'])
		return root

	def on_task_output(self, task, config):
		for entry in task.accepted:
			if 'seen' in config:
				seen.forget(entry['title'])
				log.info('Removed %s from seen database' % entry['title'])

			if 'series' in config:
				try:
					#forget_series_episode(entry['series_name'], entry['series_id'])
					log.info('Removed episode `%s` from series `%s`.' % (entry['series_id'], entry['series_name']))
				except ValueError:
    					log.debug("Series (%s) or id (%s) unknown." % (entry['series_name'],entry['series_id']))

register_plugin(OutputSeriesForget, 'series_forget', api_ver=2)
