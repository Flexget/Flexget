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
            opts = kwargs.get('options')
            output = kwargs.get('output')
            # Store the manager's options and current stdout to be restored after our execution
            if opts:
                old_opts = manager.options
                manager.options = opts
            if output:
                old_stdout = sys.stdout
                old_stderr = sys.stderr
                sys.stdout = output
                sys.stderr = output
                streamhandler = logging.StreamHandler(output)
                streamhandler.setFormatter(FlexGetFormatter())
                logging.getLogger().addHandler(streamhandler)
            try:
                manager.execute()
            finally:
                # Inform queue we are done processing this item.
                self.queue.task_done()
                # Restore manager's previous options and stdout
                if opts:
                    manager.options = old_opts
                if output:
                    print 'EOF'
                    sys.stdout = old_stdout
                    sys.stderr = old_stderr
                    logging.getLogger().removeHandler(streamhandler)

    def execute(self, **kwargs):
        """
        Adds an execution to the queue.

        keyword arguments:
        options: Values from an OptionParser to be used for this execution
        output: a BufferQueue object that will be filled with output from the execution.
        """
        if kwargs.get('output') and self.queue.unfinished_tasks:
            kwargs['output'].write('There is already an execution running. ' +
                                   'This execution will start when the previous completes.')
        self.queue.put_nowait(kwargs)
