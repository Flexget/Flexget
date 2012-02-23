import os
import shutil
import logging
import time
from flexget import validator
from flexget.plugin import register_plugin, get_plugin_by_name, DependencyError
from flexget.utils.template import RenderError

log = logging.getLogger('move')


def get_directory_size(directory):
    """
    :param directory: Path
    :return: Size in bytes (recursively)
    """
    dir_size = 0
    for (path, dirs, files) in os.walk(directory):
        for file in files:
            filename = os.path.join(path, file)
            dir_size += os.path.getsize(filename)
    return dir_size


class MovePlugin(object):

    def validator(self):
        root = validator.factory()
        root.accept('boolean')
        config = root.accept('dict')
        config.accept('path', key='to', allow_replacement=True)
        config.accept('text', key='filename')
        config.accept('boolean', key='unpack_safety')
        #config.accept('list', key='move_with').accept('text') # TODO
        config.accept('number', key='clean_source')
        return root

    def on_process_start(self, feed, config):
        """Get pathscrub method."""
        try:
            self.pathscrub = get_plugin_by_name('pathscrub').instance.scrub
        except DependencyError:
            log.warning('Move plugin cannot clean paths without pathscrub plugin.')
            self.pathscrub = lambda x: x

    def on_feed_output(self, feed, config):
        if config is True:
            config = {}
        elif config is False:
            return
        for entry in feed.accepted:
            if not 'location' in entry:
                log.warning('Cannot move `%s` because entry does not have location field.' % entry['title'])
                continue

            # SRC
            src = entry['location']
            if not os.path.exists(src):
                log.warning('Cannot move `%s` because location `%s` does not exists (anymore)' % (entry['title'], src))
                continue
            if not os.path.isfile(src):
                log.warning('Cannot move `%s` because location `%s` is not a file' % (entry['title'], src))
                continue

            # DST
            filepath, filename = os.path.split(src)
            # get proper value in order of: entry, config, above split
            dst_path = entry.get('path', config.get('to', filepath))

            if entry.get('filename') and entry['filename'] != filename:
                # entry specifies different filename than what was split from the path
                # since some inputs fill in filename it must be different in order to be used
                dst_filename = entry['filename']
            elif 'filename' in config:
                # use from configuration if given
                dst_filename = config['filename']
            else:
                # just use original filename
                dst_filename = filename

            try:
                dst_path = entry.render(dst_path)
            except RenderError:
                log.error('Path value replacement `%s` failed for `%s`' % (dst_path, entry['title']))
                continue
            try:
                dst_filename = entry.render(dst_filename)
            except RenderError:
                log.error('Filename value replacement `%s` failed for `%s`' % (dst_filename, entry['title']))
                continue
            # Clean invalid characters with pathscrub plugin
            dst_path, dst_filename = self.pathscrub(dst_path), self.pathscrub(dst_filename)

            # Join path and filename
            dst = os.path.join(dst_path, dst_filename)
            if dst == entry['location']:
                log.info('Not moving %s because source and destination are the same.' % dst)
                continue

            if not os.path.exists(dst_path):
                if feed.manager.options.test:
                    log.info('Would create `%s`' % dst_path)
                else:
                    log.info('Creating destination directory `%s`' % dst_path)
                    os.makedirs(dst_path)
            if not os.path.isdir(dst_path) and not feed.manager.options.test:
                log.warning('Cannot move `%s` because destination `%s` is not a directory' % (entry['title'], dst_path))
                continue

            if src == dst:
                log.verbose('Source and destination are same, skipping `%s`' % entry['title'])
                continue

            # unpack_safety
            if config.get('unpack_safety', entry.get('unpack_safety', True)):
                count = 0
                while True:
                    if count > 60 * 30:
                        feed.fail(entry, 'Move has been waiting unpacking for 30 minutes')
                        continue
                    size = os.path.getsize(src)
                    time.sleep(1)
                    new_size = os.path.getsize(src)
                    if size != new_size:
                        if not count % 10:
                            log.verbose('File `%s` is possibly being unpacked, waiting ...' % filename)
                    else:
                        break
                    count += 1

            # Move stuff
            if feed.manager.options.test:
                log.info('Would move `%s` to `%s`' % (src, dst))
            else:
                log.info('Moving `%s` to `%s`' % (src, dst))
                shutil.move(src, dst)
            if 'clean_source' in config:
                if not os.path.isdir(src):
                    base_path = os.path.split(src)[0]
                    size = get_directory_size(base_path) / 1024 / 1024
                    log.debug('base_path: %s size: %s' % (base_path, size))
                    if size <= config['clean_source']:
                        if feed.manager.options.test:
                            log.info('Would delete %s and everything under it' % base_path)
                        else:
                            log.info('Deleting `%s`' % base_path)
                            shutil.rmtree(base_path, ignore_errors=True)
                    else:
                        log.info(
                            'Path `%s` left because it exceeds safety value set in clean_source option' % base_path)
                else:
                    log.verbose('Cannot clean_source `%s` because source is a directory' % src)


register_plugin(MovePlugin, 'move', api_ver=2)
