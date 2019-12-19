from loguru import logger

from flexget import plugin
from flexget.event import event

from . import db

logger = logger.bind(name='series_forget')


class OutputSeriesRemove:
    schema = {'type': 'boolean'}

    def on_task_output(self, task, config):
        if not config:
            return
        for entry in task.accepted:
            if 'series_name' in entry and 'series_id' in entry:
                try:
                    db.remove_series_entity(entry['series_name'], entry['series_id'])
                    logger.info(
                        'Removed episode `{}` from series `{}` download history.',
                        entry['series_id'],
                        entry['series_name'],
                    )
                except ValueError:
                    logger.debug(
                        'Series ({}) or id ({}) unknown.', entry['series_name'], entry['series_id']
                    )


@event('plugin.register')
def register_plugin():
    plugin.register(OutputSeriesRemove, 'series_remove', api_ver=2)
