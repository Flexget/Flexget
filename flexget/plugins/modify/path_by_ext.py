from __future__ import unicode_literals, division, absolute_import
import logging
import mimetypes
from flexget.plugin import register_plugin

log = logging.getLogger('path_by_ext')


class PluginPathByExt(object):
    """
        Allows specifying path based on content-type

        Example:

        path_by_ext:
          torrent: ~/watch/torrent/
          nzb: ~/watch/nzb/
    """

    def validator(self):
        from flexget import validator
        config = validator.factory('dict')
        config.accept_any_key('any')
        return config

    def on_task_modify(self, task):
        self.ext(task, self.set_path)

    def set_path(self, entry, path):
        log.debug('Setting %s path to %s' % (entry['title'], path))
        entry['path'] = path

    def ext(self, task, callback):
        config = task.config
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
                    log.debug('Unknown mimetype %s' % entry['mime-type'])
            else:
                # try to find from url
                for ext, path in config.iteritems():
                    if entry['url'].endswith('.' + ext):
                        callback(entry, path)

register_plugin(PluginPathByExt, 'path_by_ext')
