from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import options
from flexget.event import event
from flexget.plugin import DependencyError, register_plugin

try:
    from guppy import hpy
except ImportError:
    # this will leave the plugin unloaded
    raise DependencyError(issued_by='memusage', missing='ext lib `guppy`', silent=True)

log = logging.getLogger('mem_usage')


"""
http://blog.mfabrik.com/2008/03/07/debugging-django-memory-leak-with-trackrefs-and-guppy/

# Print memory statistics
def update():
    print heapy.heap()

# Print relative memory consumption since last sycle
def update():
    print heapy.heap()
    heapy.setref()

# Print relative memory consumption w/heap traversing
def update()
    print heapy.heap().get_rp(40)
    heapy.setref()
"""


class OutputMemUsage(object):
    """Output memory usage statistics with heapy"""

    def __init__(self):
        self.heapy = None

    schema = {'type': 'boolean'}

    def on_process_start(self, task):
        if not task.options.mem_usage:
            return
        # start only once
        if self.heapy:
            return
        self.heapy = hpy()

    def on_process_end(self, task):
        if not task.options.mem_usage:
            return
        # prevents running this multiple times ...
        if not self.heapy:
            return
        print 'Calculating memory usage:'
        print self.heapy.heap()
        print '-' * 79
        print self.heapy.heap().get_rp(40)
        self.heapy = None


register_plugin(OutputMemUsage, 'mem_usage', builtin=True)


@event('options.register')
def register_parser_arguments():
    options.get_parser('execute').add_argument('--mem-usage', action='store_true', dest='mem_usage', default=False,
                                               help='display memory usage debug information')
