from loguru import logger

from flexget import plugin
from flexget.entry import register_lazy_lookup
from flexget.event import event

logger = logger.bind(name='metainfo_media_id')


class MetainfoMediaId:
    """
    Populate media_id field based on media type etc.
    """

    schema = {'type': 'boolean'}

    @plugin.priority(0)  # run after other metainfo plugins
    def on_task_metainfo(self, task, config):
        # Don't run if we are disabled
        if config is False:
            return
        for entry in task.entries:
            entry.add_lazy_fields(self.get_media_id, ['media_id'])

    @register_lazy_lookup('media_id')
    def get_media_id(self, entry):
        # Try to generate a media id based on available parser fields
        media_id = None
        if entry.get('movie_name'):
            media_id = entry['movie_name']
            if entry.get('movie_year'):
                media_id = f'{media_id} {entry["movie_year"]}'
        elif entry.get('series_name'):
            media_id = entry['series_name']
            if entry.get('series_year'):
                media_id = f'{media_id} {entry["series_year"]}'

            if entry.get('series_episode'):
                media_id = f'{media_id} S{(entry.get("series_season") or 0):02}E{entry["series_episode"]:02}'
            elif entry.get('series_season'):
                media_id = f'{media_id} S{entry["series_season"]:02}E00'
            elif entry.get('series_date'):
                media_id = f'{media_id} {entry["series_date"]}'
            else:
                # We do not want a media id for series
                media_id = None

        if media_id:
            media_id = media_id.strip().lower()

        entry['media_id'] = media_id


@event('plugin.register')
def register_plugin():
    plugin.register(MetainfoMediaId, 'metainfo_media_id', api_ver=2, builtin=True)
