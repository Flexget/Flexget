import os

from loguru import logger

from flexget import plugin
from flexget.event import event
from flexget.utils.pathscrub import pathscrub
from flexget.utils.template import RenderError, render_from_entry

logger = logger.bind(name='symlink')


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
            linkfrom = entry['location']
            linkfrom_path, linkfrom_name = os.path.split(linkfrom)

            # get the proper path and name in order of: entry, config, above split
            linkto_path = entry.get('link_to', config.get('to', linkfrom_path))
            if config.get('rename'):
                linkto_name = config['rename']
            elif entry.get('filename') and entry['filename'] != linkfrom_name:
                # entry specifies different filename than what was split from the path
                # since some inputs fill in filename it must be different in order to be used
                linkto_name = entry['filename']
            else:
                linkto_name = linkfrom_name

            try:
                linkto_path = entry.render(linkto_path)
            except RenderError as err:
                raise plugin.PluginError(
                    'Path value replacement `%s` failed: %s' % (linkto_path, err.args[0])
                )
            try:
                linkto_name = entry.render(linkto_name)
            except RenderError as err:
                raise plugin.PluginError(
                    'Filename value replacement `%s` failed: %s' % (linkto_name, err.args[0])
                )

            # Clean invalid characters with pathscrub plugin
            linkto_path = pathscrub(os.path.expanduser(linkto_path))
            linkto_name = pathscrub(linkto_name, filename=True)

            # Join path and filename
            linkto = os.path.join(linkto_path, linkto_name)
            if linkto == entry['location']:
                raise plugin.PluginWarning('source and destination are the same.')

            # Hardlinks for dirs will not be failed here
            if os.path.exists(linkto) and (
                config['link_type'] == 'soft' or os.path.isfile(linkfrom)
            ):
                msg = 'Symlink destination %s already exists' % linkto
                if existing == 'ignore':
                    logger.verbose(msg)
                else:
                    entry.fail(msg)
                continue
            logger.verbose('{}link `{}` to `{}`', config['link_type'], linkfrom, linkto)
            try:
                if config['link_type'] == 'soft':
                    os.symlink(linkfrom, linkto)
                else:
                    if os.path.isdir(linkfrom):
                        self.hard_link_dir(linkfrom, linkto, existing)
                    else:
                        dirname = os.path.dirname(linkto)
                        if not os.path.exists(dirname):
                            os.makedirs(dirname)
                        os.link(linkfrom, linkto)
            except OSError as e:
                entry.fail('Failed to create %slink, %s' % (config['link_type'], e))

    def hard_link_dir(self, path, destination, existing):
        if not os.path.exists(destination):
            try:
                os.makedirs(destination)
            except OSError as e:
                # Raised when it already exists, but are there other cases?
                logger.debug('Failed to create destination dir {}: {}', destination, e)
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
                    logger.debug('Failed to create subdir {}: {}', d, e)
            for f in files:
                src_file = os.path.join(root, f)
                dst_file = os.path.join(dst_dir, f)
                logger.debug('Hardlinking {} to {}', src_file, dst_file)
                try:
                    os.link(src_file, dst_file)
                except OSError as e:
                    logger.debug('Failed to create hardlink for file {}: {}', f, e)
                    if existing == 'fail':
                        raise  # reraise to fail the entry in the calling function

        os.chdir(working_dir)


@event('plugin.register')
def register_plugin():
    if os.name == 'nt':
        logger.trace('Symlinks not supported on Windows. Skipping Symlink plugin register.')
        return
    plugin.register(Symlink, 'symlink', api_ver=2)
