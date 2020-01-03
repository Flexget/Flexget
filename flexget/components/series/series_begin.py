from loguru import logger

from flexget import plugin
from flexget.event import event

from . import db

logger = logger.bind(name='set_series_begin')


class SetSeriesBegin:
    """
    Set the first episode for series. Uses series_name and series_id.

    Example::

      set_series_begin: yes

    """

    schema = {'type': 'boolean'}

    def on_task_output(self, task, config):
        if not (config and task.accepted):
            return
        for entry in task.accepted:
            if entry.get('series_name') and entry.get('series_id'):
                fshow = (
                    task.session.query(db.Series)
                    .filter(db.Series.name == entry['series_name'])
                    .first()
                )
                if not fshow:
                    fshow = db.Series()
                    fshow.name = entry['series_name']
                    task.session.add(fshow)
                try:
                    db.set_series_begin(fshow, entry['series_id'])
                except ValueError as e:
                    logger.error(
                        'An error occurred trying to set begin for {}: {}', entry['series_name'], e
                    )
                logger.info(
                    'First episode for "{}" set to {}', entry['series_name'], entry['series_id']
                )


@event('plugin.register')
def register_plugin():
    plugin.register(SetSeriesBegin, 'set_series_begin', api_ver=2)
