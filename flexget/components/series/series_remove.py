from loguru import logger

from flexget import plugin
from flexget.event import event

from . import db

logger = logger.bind(name='series_remove')


class OutputSeriesRemove:
    schema = {
        'oneOf': [
            {'type': 'boolean'},
            {'type': 'object', 'properties': {'forget': {'type': 'boolean'}}},
        ],
    }

    def on_task_output(self, task, config):
        if not config:
            return
        if isinstance(config, bool):
            config = {'forget': False}
        forget = config['forget']

        for entry in task.accepted:
            if 'series_name' in entry:
                if 'series_id' in entry:
                    try:
                        db.remove_series_entity(entry['series_name'], entry['series_id'], forget)
                        logger.info(
                            'Removed {}episode `{}` from series `{}` download history.',
                            'and forgot ' if forget else '',
                            entry['series_id'],
                            entry['series_name'],
                        )
                    except ValueError:
                        logger.debug(
                            'Series ({}) or id ({}) unknown.',
                            entry['series_name'],
                            entry['series_id'],
                        )
                else:
                    try:
                        db.remove_series(entry['series_name'], forget)
                        logger.info(
                            'Removed {}series `{}` download history.',
                            'and forgot ' if forget else '',
                            entry['series_name'],
                        )
                    except ValueError:
                        logger.debug('Series ({}) unknown.', entry['series_name'])


@event('plugin.register')
def register_plugin():
    plugin.register(OutputSeriesRemove, 'series_remove', api_ver=2)
