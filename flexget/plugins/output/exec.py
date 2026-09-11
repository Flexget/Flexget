import subprocess

from loguru import logger

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.template import (
    RenderError,
    filter_shell_quote,
    render_from_entry,
    render_from_task,
)
from flexget.utils.tools import io_encoding

logger = logger.bind(name='exec')


class EscapingEntry(Entry):
    """Copy of an Entry whose string field values are pre-quoted for safe use in a shell command line.

    Used by the `auto_escape` option. The store is populated directly
    (bypassing Entry's normal per-field __setitem__ coercion, e.g.
    `location` -> `Path`) so the quoting survives untouched. Disposable,
    one-shot rendering context only -- not a real Entry (no accept/reject/fail
    state).
    """

    def __init__(self, entry: Entry) -> None:
        super().__init__()
        self.store = {
            key: filter_shell_quote(value) if isinstance(value, str) else value
            for key, value in entry.store.items()
        }
        self.task = entry.task


class PluginExec:
    """Execute commands.

    Simple example, execute command for entries that reach output::

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

    Security
    --------
    Commands run in a real shell (``shell=True``). Entry fields (``title``,
    ``url``, and anything else that came from a feed/site) are
    attacker-controlled: a malicious feed can put shell metacharacters
    (backticks, ``$()``, ``;``, ``|``, quotes, newlines, ...) in a field and
    have them run as part of your command. This does not apply to the
    ``phase`` key, which templates from the task rather than an entry.

    To safely substitute untrusted entry fields, either:

    - Set ``auto_escape: yes`` to shell-quote every substituted entry field
      automatically::

        exec:
          auto_escape: yes
          on_output:
            for_accepted: echo 'accepted {{title}}' >> log.txt

    - Or apply the ``shell_quote`` filter to individual fields (works
      everywhere, including ``phase:``)::

        exec:
          on_output:
            for_accepted: echo {{title|shell_quote}} >> log.txt

    Important: do not wrap an escaped field in your own quotes
    (``"{{title}}"`` or ``'{{title}}'``). That is not just redundant, it can
    reopen the hole: a backtick is still expanded by the shell inside double
    quotes, and an embedded quote from the escaping can break out of your own
    single quotes. Leave the field bare (or adjacent to plain unquoted text,
    e.g. ``/path/{{title|shell_quote}}``).

    Neither option protects shell syntax *you* write literally: ``;``,
    ``|``, ``>``, backticks etc. that you type yourself in the command are
    still your responsibility. They only ensure a substituted value can't
    break out of its own token to run something else.
    """

    NAME = 'exec'
    HANDLED_PHASES = ['start', 'input', 'filter', 'output', 'exit']

    schema = {
        'oneOf': [
            one_or_more({'type': 'string'}),
            {
                'type': 'object',
                'properties': {
                    'on_start': {'$ref': '#/$defs/phaseSettings'},
                    'on_input': {'$ref': '#/$defs/phaseSettings'},
                    'on_filter': {'$ref': '#/$defs/phaseSettings'},
                    'on_output': {'$ref': '#/$defs/phaseSettings'},
                    'on_exit': {'$ref': '#/$defs/phaseSettings'},
                    'fail_entries': {'type': 'boolean'},
                    'auto_escape': {'type': 'boolean'},
                    'encoding': {'type': 'string'},
                    'allow_background': {'type': 'boolean'},
                },
                'additionalProperties': False,
            },
        ],
        '$defs': {
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
                                'Entry `{}` does not have required fields for string replacement.'.format(
                                    entry['title']
                                )
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
        """Create methods to handle task phases."""
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
