from __future__ import unicode_literals, division, absolute_import
from argparse import Namespace
from copy import copy
import logging
import sys
import threading
from Queue import Queue

from flexget.logger import FlexGetFormatter
from flexget.options import CoreArgumentParser

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
            output = kwargs.pop('output', None)
            # make copy of original options and apply options from opts
            old_opts = copy(manager.options)
            # Start with the exec defaults, to make sure all exec subcommand options are defined
            new_opts = CoreArgumentParser().get_subparser('execute').parse_args().__dict__
            new_opts.update(old_opts.__dict__)
            if opts:
                if isinstance(opts, Namespace):
                    opts = opts.__dict__
                new_opts.update(opts)
            manager.options.__dict__.update(new_opts)
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
                manager.options = old_opts
                if output:
                    # Write EOF to the output, so that a listener knows when the output is over
                    output.write('EOF')
                    sys.stdout = old_stdout
                    sys.stderr = old_stderr
                    logging.getLogger().removeHandler(streamhandler)

    def execute(self, **kwargs):
        """
        Adds an execution to the queue.

        keyword arguments:

        options: dict or argparse.Namespace object with CLI options for this execution
        output: a BufferQueue object that will be filled with output from the execution.

        all other keyword arguments will be passed to manager.execute
        """

        if 'options' in kwargs and not isinstance(kwargs['options'], (dict, Namespace)):
            raise TypeError('options should be a dict or Namespace, got %s' % type(kwargs['options']))

        if 'tasks' in kwargs and not hasattr(kwargs['tasks'], '__iter__'):
            raise TypeError('tasks should be iterable, got %s' % type(kwargs['tasks']))

        if kwargs.get('output') and self.queue.unfinished_tasks:
            kwargs['output'].write('There is already an execution running. ' +
                                   'This execution will start when the previous completes.')
        self.queue.put_nowait(kwargs)
