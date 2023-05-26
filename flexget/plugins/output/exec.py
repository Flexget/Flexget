import subprocess

from loguru import logger

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.template import RenderError, render_from_entry, render_from_task
from flexget.utils.tools import io_encoding

logger = logger.bind(name='exec')


class EscapingEntry(Entry):
    """Helper class, same as a Entry, but returns all string value with quotes escaped."""

    def __init__(self, entry):
        super().__init__(entry)

    def __getitem__(self, key):
        value = super().__getitem__(key)
        # TODO: May need to be different depending on OS
        if isinstance(value, str):
            value = value.replace('"', '\\"')
        return value


class PluginExec:
    """
    Execute commands

    Simple example, xecute command for entries that reach output::

      exec: echo 'found {{title}} at {{url}}' > file

    Advanced Example::

      exec:
        on_start:
          phase: echo "Started"
        on_input:
          for_entries: echo 'got {{title}}'
        on_output:
          for_accepted: echo 'accepted {{title}} - {{url}} > file

    You can use all (available) entry fields in the command.
    """

    NAME = 'exec'
    HANDLED_PHASES = ['start', 'input', 'filter', 'output', 'exit']

    schema = {
        'oneOf': [
            one_or_more({'type': 'string'}),
            {
                'type': 'object',
                'properties': {
                    'on_start': {'$ref': '#/definitions/phaseSettings'},
                    'on_input': {'$ref': '#/definitions/phaseSettings'},
                    'on_filter': {'$ref': '#/definitions/phaseSettings'},
                    'on_output': {'$ref': '#/definitions/phaseSettings'},
                    'on_exit': {'$ref': '#/definitions/phaseSettings'},
                    'fail_entries': {'type': 'boolean'},
                    'auto_escape': {'type': 'boolean'},
                    'encoding': {'type': 'string'},
                    'allow_background': {'type': 'boolean'},
                },
                'additionalProperties': False,
            },
        ],
        'definitions': {
            'phaseSettings': {
                'type': 'object',
                'properties': {
                    'phase': one_or_more({'type': 'string'}),
                    'for_entries': one_or_more({'type': 'string'}),
                    'for_accepted': one_or_more({'type': 'string'}),
                    'for_rejected': one_or_more({'type': 'string'}),
                    'for_undecided': one_or_more({'type': 'string'}),
                    'for_failed': one_or_more({'type': 'string'}),
                },
                'additionalProperties': False,
            }
        },
    }

    def prepare_config(self, config):
        if isinstance(config, str):
            config = [config]
        if isinstance(config, list):
            config = {'on_output': {'for_accepted': config}}
        if not config.get('encoding'):
            config['encoding'] = io_encoding
        for phase_name in config:
            if phase_name.startswith('on_'):
                for items_name in config[phase_name]:
                    if isinstance(config[phase_name][items_name], str):
                        config[phase_name][items_name] = [config[phase_name][items_name]]

        return config

    def execute_cmd(self, cmd, allow_background, encoding):
        logger.verbose('Executing: {}', cmd)
        p = subprocess.Popen(
            cmd,
            shell=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            close_fds=False,
        )
        if not allow_background:
            r, w = (p.stdout, p.stdin)
            response = r.read().decode(io_encoding)
            r.close()
            w.close()
            if response:
                logger.info('Stdout: {}', response.rstrip())  # rstrip to get rid of newlines
        return p.wait()

    def execute(self, task, phase_name, config):
        config = self.prepare_config(config)
        if phase_name not in config:
            logger.debug('phase {} not configured', phase_name)
            return

        name_map = {
            'for_entries': task.entries,
            'for_accepted': task.accepted,
            'for_rejected': task.rejected,
            'for_undecided': task.undecided,
            'for_failed': task.failed,
        }

        allow_background = config.get('allow_background')
        for operation, entries in name_map.items():
            if operation not in config[phase_name]:
                continue

            logger.debug(
                'running phase_name: {} operation: {} entries: {}',
                phase_name,
                operation,
                len(entries),
            )

            for entry in entries:
                for cmd in config[phase_name][operation]:
                    entrydict = EscapingEntry(entry) if config.get('auto_escape') else entry
                    # Do string replacement from entry, but make sure quotes get escaped
                    try:
                        cmd = render_from_entry(cmd, entrydict)
                    except RenderError as e:
                        logger.error('Could not set exec command for {}: {}', entry['title'], e)
                        # fail the entry if configured to do so
                        if config.get('fail_entries'):
                            entry.fail(
                                'Entry `%s` does not have required fields for string replacement.'
                                % entry['title']
                            )
                        continue

                    logger.debug(
                        'phase_name: {} operation: {} cmd: {}', phase_name, operation, cmd
                    )
                    if task.options.test:
                        logger.info('Would execute: {}', cmd)
                    else:
                        # Make sure the command can be encoded into appropriate encoding, don't actually encode yet,
                        # so logging continues to work.
                        try:
                            cmd.encode(config['encoding'])
                        except UnicodeEncodeError:
                            logger.error(
                                'Unable to encode cmd `{}` to {}', cmd, config['encoding']
                            )
                            if config.get('fail_entries'):
                                entry.fail(
                                    'cmd `{}` could not be encoded to {}.'.format(
                                        cmd, config['encoding']
                                    )
                                )
                            continue
                        # Run the command, fail entries with non-zero return code if configured to
                        if self.execute_cmd(
                            cmd, allow_background, config['encoding']
                        ) != 0 and config.get('fail_entries'):
                            entry.fail('exec return code was non-zero')

        # phase keyword in this
        if 'phase' in config[phase_name]:
            for cmd in config[phase_name]['phase']:
                try:
                    cmd = render_from_task(cmd, task)
                except RenderError as e:
                    logger.error('Error rendering `{}`: {}', cmd, e)
                else:
                    logger.debug('phase cmd: {}', cmd)
                    if task.options.test:
                        logger.info('Would execute: {}', cmd)
                    else:
                        self.execute_cmd(cmd, allow_background, config['encoding'])

    def __getattr__(self, item):
        """Creates methods to handle task phases."""
        for phase in self.HANDLED_PHASES:
            if item == plugin.phase_methods[phase]:
                # A phase method we handle has been requested
                break
        else:
            # We don't handle this phase
            raise AttributeError(item)

        def phase_handler(task, config):
            self.execute(task, 'on_' + phase, config)

        # Make sure we run after other plugins so exec can use their output
        phase_handler.priority = 100
        return phase_handler


@event('plugin.register')
def register_plugin():
    plugin.register(PluginExec, 'exec', api_ver=2)
