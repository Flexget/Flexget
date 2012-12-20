from __future__ import unicode_literals, division, absolute_import
from copy import copy
import logging
import sys
import threading
from Queue import Queue
from flexget.logger import FlexGetFormatter

log = logging.getLogger('ui.executor')


class BufferQueue(Queue):

    def write(self, txt):
        txt = txt.rstrip('\n')
        if txt:
            self.put_nowait(txt)


class ExecThread(threading.Thread):
    """Thread that does the execution. It can accept options with an execution, and queues execs if necessary."""

    def __init__(self):
        threading.Thread.__init__(self)
        self.daemon = True
        self.queue = Queue()

    def run(self):
        from flexget.ui.webui import manager
        while True:
            kwargs = self.queue.get() or {}
            opts = kwargs.pop('options', None)
            parsed_options = kwargs.pop('parsed_options', None)
            output = kwargs.pop('output', None)
            if opts:
                # make copy of original options and apply options from opts
                old_opts = copy(manager.options)
                self._apply_options(manager.options, opts)
            if parsed_options:
                old_opts = manager.options
                manager.options = parsed_options
            if output:
                old_stdout = sys.stdout
                old_stderr = sys.stderr
                sys.stdout = output
                sys.stderr = output
                # TODO: Use a filter to capture only the logging for this execution
                streamhandler = logging.StreamHandler(output)
                streamhandler.setFormatter(FlexGetFormatter())
                logging.getLogger().addHandler(streamhandler)
            try:
                manager.execute(**kwargs)
            finally:
                # Inform queue we are done processing this item.
                self.queue.task_done()
                # Restore manager's previous options and stdout
                if opts:
                    manager.options = old_opts
                if output:
                    # Write EOF to the output, so that a listener knows when the output is over
                    output.write('EOF')
                    sys.stdout = old_stdout
                    sys.stderr = old_stderr
                    logging.getLogger().removeHandler(streamhandler)

    def _apply_options(self, parser, options):
        """Applies dict :options: to ArgParse parser results"""

        for name, value in options.iteritems():
            if hasattr(parser, name):
                log.debug('setting options %s to %s' % (name, value))
                setattr(parser, name, value)
            else:
                log.error('Option %s does not exist, ignoring it' % name)

    def execute(self, **kwargs):
        """
        Adds an execution to the queue.

        keyword arguments:

        options: Dict containing option, value pairs for this execution
        parsed_options: Parsed OptionParser to be used for this execution
        output: a BufferQueue object that will be filled with output from the execution.

        all other keyword arguments will be passed to manager.execute
        kwargs options and parsed_options are mutually exclusive
        """

        if 'options' in kwargs and not isinstance(kwargs['options'], dict):
            raise TypeError('options should be a dict, got %s' % type(kwargs['options']))

        if 'tasks' in kwargs and not hasattr(kwargs['tasks'], '__iter__'):
            raise TypeError('tasks should be iterable, got %s' % type(kwargs['tasks']))

        if 'options' in kwargs and 'parsed_options' in kwargs:
            raise ValueError('options and parsed_options are mutually exclusive')

        if kwargs.get('output') and self.queue.unfinished_tasks:
            kwargs['output'].write('There is already an execution running. ' +
                                   'This execution will start when the previous completes.')
        self.queue.put_nowait(kwargs)
