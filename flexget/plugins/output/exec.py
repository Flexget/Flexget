from __future__ import unicode_literals, division, absolute_import
import subprocess
import logging
import sys
from UserDict import UserDict
from flexget.plugin import register_plugin, phase_methods
from flexget.utils.template import render_from_entry, render_from_task, RenderError

log = logging.getLogger('exec')


class EscapingDict(UserDict):
    """Helper class, same as a dict, but returns all string value with quotes escaped."""

    def __getitem__(self, key):
        value = self.data[key]
        if isinstance(value, basestring):
            # TODO: May need to be different depending on OS
            value = value.replace('"', '\\"')
            #value = re.escape(value)
        return value


class PluginExec(object):
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
            {'type': 'string'},
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
                    'allow_background': {'type': 'boolean'}
                },
                'additionalProperties': False
            }
        ],
        'definitions': {
            'phaseSettings': {
                'type': 'object',
                'properties': {
                    'phase': {'type': 'string'},
                    'for_entries': {'type': 'string'},
                    'for_accepted': {'type': 'string'},
                    'for_rejected': {'type': 'string'},
                    'for_failed': {'type': 'string'}
                },
                'additionalProperties': False
            }
        }
    }

    def prepare_config(self, config):
        if isinstance(config, basestring):
            config = {'on_output': {'for_accepted': config}}
        if not config.get('encoding'):
            config['encoding'] = sys.getfilesystemencoding()
        return config

    def execute_cmd(self, cmd, allow_background, encoding):
        log.verbose('Executing: %s' % cmd)
        p = subprocess.Popen(cmd.encode(encoding), shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, close_fds=False)
        if not allow_background:
            (r, w) = (p.stdout, p.stdin)
            response = r.read()
            r.close()
            w.close()
            if response:
                log.info('Stdout: %s' % response)
        return p.wait()

    def execute(self, task, phase_name, config):
        config = self.prepare_config(config)
        if not phase_name in config:
            log.debug('phase %s not configured' % phase_name)
            return

        name_map = {'for_entries': task.entries, 'for_accepted': task.accepted,
                    'for_rejected': task.rejected, 'for_failed': task.failed}

        allow_background = config.get('allow_background')
        for operation, entries in name_map.iteritems():
            if not operation in config[phase_name]:
                continue

            log.debug('running phase_name: %s operation: %s entries: %s' % (phase_name, operation, len(entries)))

            for entry in entries:
                cmd = config[phase_name][operation]
                entrydict = EscapingDict(entry) if config.get('auto_escape') else entry
                # Do string replacement from entry, but make sure quotes get escaped
                try:
                    cmd = render_from_entry(cmd, entrydict)
                except RenderError as e:
                    log.error('Could not set exec command for %s: %s' % (entry['title'], e))
                    # fail the entry if configured to do so
                    if config.get('fail_entries'):
                        entry.fail('Entry `%s` does not have required fields for string replacement.' % entry['title'])
                    continue

                log.debug('phase_name: %s operation: %s cmd: %s' % (phase_name, operation, cmd))
                if task.manager.options.test:
                    log.info('Would execute: %s' % cmd)
                else:
                    # Make sure the command can be encoded into appropriate encoding, don't actually encode yet,
                    # so logging continues to work.
                    try:
                        cmd.encode(config['encoding'])
                    except UnicodeEncodeError:
                        log.error('Unable to encode cmd `%s` to %s' % (cmd, config['encoding']))
                        if config.get('fail_entries'):
                            entry.fail('cmd `%s` could not be encoded to %s.' % (cmd, config['encoding']))
                        continue
                    # Run the command, fail entries with non-zero return code if configured to
                    if self.execute_cmd(cmd, allow_background, config['encoding']) != 0 and config.get('fail_entries'):
                        entry.fail('exec return code was non-zero')

        # phase keyword in this
        if 'phase' in config[phase_name]:
            cmd = config[phase_name]['phase']
            try:
                cmd = render_from_task(cmd, task)
            except RenderError as e:
                log.error('Error rendering `%s`: %s' % (cmd, e))
            else:
                log.debug('phase cmd: %s' % cmd)
                if task.manager.options.test:
                    log.info('Would execute: %s' % cmd)
                else:
                    self.execute_cmd(cmd, allow_background, config['encoding'])

    def __getattr__(self, item):
        """Creates methods to handle task phases."""
        for phase in self.HANDLED_PHASES:
            if item == phase_methods[phase]:
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


register_plugin(PluginExec, 'exec', api_ver=2)
