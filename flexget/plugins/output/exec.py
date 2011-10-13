import subprocess
import logging
import re
from UserDict import UserDict
from flexget.plugin import register_plugin, priority
from flexget.utils.tools import replace_from_entry

log = logging.getLogger('exec')


class EscapingDict(UserDict):
    """Helper class, same as a dict, but returns all string value with quotes escaped."""

    def __getitem__(self, key):
        value = self.data[key]
        if isinstance(value, basestring):
            value = re.escape(value)
        return value


class PluginExec(object):
    """
    Execute commands

    Simple Example:
    Execute command for entries that reach output.

    exec: echo 'found %(title)s at %(url)s' > file

    Advanced Example:

    exec:
      on_start:
        phase: echo "Started"
      on_input:
        for_entries: echo 'got %(title)s'
      on_output:
        for_accepted: echo 'accepted %(title)s - %(url)s > file

    You can use all (available) entry fields in the command.
    """

    NAME = 'exec'

    def validator(self):
        from flexget import validator
        root = validator.factory('root')
        # Simple format, runs on_output for_accepted
        root.accept('text')

        # Advanced format
        adv = root.accept('dict')

        def add(name):
            phase = adv.accept('dict', key=name)
            phase.accept('text', key='phase')
            phase.accept('text', key='for_entries')
            phase.accept('text', key='for_accepted')
            phase.accept('text', key='for_rejected')
            phase.accept('text', key='for_failed')

        for name in ['on_start', 'on_input', 'on_filter', 'on_output', 'on_exit']:
            add(name)

        adv.accept('boolean', key='fail_entries')
        adv.accept('boolean', key='auto_escape')
        adv.accept('boolean', key='allow_background')

        return root

    def get_config(self, feed):
        config = feed.config[self.NAME]
        if isinstance(config, basestring):
            config = {'on_output': {'for_accepted': feed.config[self.NAME]}}
        return config

    def on_feed_start(self, feed):
        self.execute(feed, 'on_start')

    # Make sure we run after other plugins so exec can use their output
    @priority(100)
    def on_feed_input(self, feed):
        self.execute(feed, 'on_input')

    # Make sure we run after other plugins so exec can use their output
    @priority(100)
    def on_feed_filter(self, feed):
        self.execute(feed, 'on_filter')

    # Make sure we run after other plugins so exec can use their output
    @priority(100)
    def on_feed_output(self, feed):
        self.execute(feed, 'on_output')

    def on_feed_exit(self, feed):
        self.execute(feed, 'on_exit')

    def execute_cmd(self, cmd, allow_background):
        log.verbose('Executing: %s' % cmd)
        p = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, close_fds=False)
        if not allow_background:
            (r, w) = (p.stdout, p.stdin)
            response = r.read()
            r.close()
            w.close()
            if response:
                log.info('Stdout: %s' % response)
        return p.wait()

    def execute(self, feed, phase_name):
        config = self.get_config(feed)
        if not phase_name in config:
            log.debug('phase %s not configured' % phase_name)
            return

        name_map = {'for_entries': feed.entries, 'for_accepted': feed.accepted,
                    'for_rejected': feed.rejected, 'for_failed': feed.failed}

        allow_background = config.get('allow_background')
        for operation, entries in name_map.iteritems():
            if not operation in config[phase_name]:
                continue

            log.debug('running phase_name: %s operation: %s entries: %s' % (phase_name, operation, len(entries)))

            for entry in entries:
                cmd = config[phase_name][operation]
                entrydict = EscapingDict(entry) if config.get('auto_escape') else entry
                # Do string replacement from entry, but make sure quotes get escaped
                cmd = replace_from_entry(cmd, entrydict, 'exec command', log.error, default=None)
                if cmd is None:
                    # fail the entry if configured to do so
                    if config.get('fail_entries'):
                        feed.fail(entry, 'Entry `%s` does not have required fields for string replacement.' %
                                         entry['title'])
                    continue

                log.debug('phase_name: %s operation: %s cmd: %s' % (phase_name, operation, cmd))
                if feed.manager.options.test:
                    log.info('Would execute: %s' % cmd)
                else:
                    # Run the command, fail entries with non-zero return code if configured to
                    if self.execute_cmd(cmd, allow_background) != 0 and config.get('fail_entries'):
                        feed.fail(entry, "exec return code was non-zero")

        # phase keyword in this
        if 'phase' in config[phase_name]:
            cmd = config[phase_name]['phase']
            log.debug('phase cmd: %s' % cmd)
            if feed.manager.options.test:
                log.info('Would execute: %s' % cmd)
            else:
                self.execute_cmd(cmd, allow_background)


register_plugin(PluginExec, 'exec')
