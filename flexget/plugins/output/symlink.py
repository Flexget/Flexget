import logging
import os

from flexget import plugin
from flexget.event import event
from flexget.utils.pathscrub import pathscrub
from flexget.utils.template import RenderError, render_from_entry

log = logging.getLogger('symlink')


class Symlink:

    schema = {
        'oneOf': [
            {
                'title': 'specify options',
                'type': 'object',
                'properties': {
                    'to': {'type': 'string', 'format': 'path'},
                    'rename': {'type': 'string'},
                    'existing': {'type': 'string', 'enum': ['ignore', 'fail']},
                    'link_type': {'type': 'string', 'enum': ['soft', 'hard']},
                },
                'required': ['to'],
                'additionalProperties': False,
            },
            {'title': 'specify path', 'type': 'string', 'format': 'path'},
        ]
    }

    destination_field = 'link_to'

    def prepare_config(self, config):
        if not isinstance(config, dict):
            config = {'to': config}

        config.setdefault('existing', 'fail')
        config.setdefault('link_type', 'soft')

        return config

    @plugin.priority(0)
    def on_task_output(self, task, config):
        if not config:
            return
        config = self.prepare_config(config)
        existing = config['existing']
        for entry in task.accepted:
            if 'location' not in entry:
                entry.fail('Does not have location field for symlinking')
                continue
            lnkfrom = entry['location']
            lnkfrom_path, lnkfrom_name = os.path.split(lnkfrom)
            
            # get the proper path and name in order of: entry, config, above split
            lnkto_path = entry.get(self.destination_field, config.get('to', lnkfrom_path))
            if config.get('rename'):
                lnkto_name = config['rename']
            elif entry.get('filename') and entry['filename'] != lnkfrom_name:
                # entry specifies different filename than what was split from the path
                # since some inputs fill in filename it must be different in order to be used
                lnkto_name = entry['filename']
            else:
                lnkto_name = lnkfrom_name

            try:
                lnkto_path = entry.render(lnkto_path)
            except RenderError as err:
                raise plugin.PluginError(
                    'Path value replacement `%s` failed: %s' % (lnkto_path, err.args[0])
                )
            try:
                lnkto_name = entry.render(lnkto_name)
            except RenderError as err:
                raise plugin.PluginError(
                    'Filename value replacement `%s` failed: %s' % (lnkto_name, err.args[0])
                )

            # Clean invalid characters with pathscrub plugin
            lnkto_path = pathscrub(os.path.expanduser(lnkto_path))
            lnkto_name = pathscrub(lnkto_name, filename=True)

            # Join path and filename
            lnkto = os.path.join(lnkto_path, lnkto_name)
            if lnkto == entry['location']:
                raise plugin.PluginWarning('source and destination are the same.')

            # Hardlinks for dirs will not be failed here
            if os.path.exists(lnkto) and (
                config['link_type'] == 'soft' or os.path.isfile(lnkfrom)
            ):
                msg = 'Symlink destination %s already exists' % lnkto
                if existing == 'ignore':
                    log.verbose(msg)
                else:
                    entry.fail(msg)
                continue
            log.verbose('%slink `%s` to `%s`', config['link_type'], lnkfrom, lnkto)
            try:
                if config['link_type'] == 'soft':
                    os.symlink(lnkfrom, lnkto)
                else:
                    if os.path.isdir(lnkfrom):
                        self.hard_link_dir(lnkfrom, lnkto, existing)
                    else:
                        dirname = os.path.dirname(lnkto)
                        if not os.path.exists(dirname):
                            os.makedirs(dirname)
                        os.link(lnkfrom, lnkto)
            except OSError as e:
                entry.fail('Failed to create %slink, %s' % (config['link_type'], e))

    def hard_link_dir(self, path, destination, existing):
        if not os.path.exists(destination):
            try:
                os.makedirs(destination)
            except OSError as e:
                # Raised when it already exists, but are there other cases?
                log.debug('Failed to create destination dir %s: %s', destination, e)
        # 'recursively' traverse and hard link
        working_dir = os.getcwd()
        os.chdir(path)  # change working dir to make dir joins easier
        for root, dirs, files in os.walk('.'):
            dst_dir = os.path.abspath(os.path.join(destination, root))
            for d in dirs:
                try:
                    os.mkdir(d)
                except OSError as e:
                    # Raised when it already exists, but are there other cases?
                    log.debug('Failed to create subdir %s: %s', d, e)
            for f in files:
                src_file = os.path.join(root, f)
                dst_file = os.path.join(dst_dir, f)
                log.debug('Hardlinking %s to %s', src_file, dst_file)
                try:
                    os.link(src_file, dst_file)
                except OSError as e:
                    log.debug('Failed to create hardlink for file %s: %s', f, e)
                    if existing == 'fail':
                        raise  # reraise to fail the entry in the calling function

        os.chdir(working_dir)


@event('plugin.register')
def register_plugin():
    if os.name == 'nt':
        log.trace('Symlinks not supported on Windows. Skipping Symlink plugin register.')
        return
    plugin.register(Symlink, 'symlink', api_ver=2)
