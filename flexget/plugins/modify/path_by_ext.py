import mimetypes

from loguru import logger

from flexget import plugin
from flexget.event import event

logger = logger.bind(name='path_by_ext')


class PluginPathByExt:
    """
    Allows specifying path based on content-type

    Example:

    path_by_ext:
      torrent: ~/watch/torrent/
      nzb: ~/watch/nzb/
    """

    schema = {'type': 'object'}

    def on_task_modify(self, task, config):
        self.ext(task, config, self.set_path)

    def set_path(self, entry, path):
        logger.debug('Setting {} path to {}', entry['title'], path)
        entry['path'] = path

    def ext(self, task, config, callback):
        for entry in task.entries:
            if 'mime-type' in entry:
                # check if configuration has mimetype that entry has
                if entry['mime-type'] in config:
                    callback(entry, config[entry['mime-type']])
                # check if entry mimetype extension matches in config
                ext = mimetypes.types_map.get(entry['mime-type'])
                path = config.get(ext) or config.get(ext[1:])
                if path:
                    callback(entry, path)
                else:
                    logger.debug('Unknown mimetype {}', entry['mime-type'])
            else:
                # try to find from url
                for ext, path in config.items():
                    if entry['url'].endswith('.' + ext):
                        callback(entry, path)


@event('plugin.register')
def register_plugin():
    plugin.register(PluginPathByExt, 'path_by_ext', api_ver=2)
