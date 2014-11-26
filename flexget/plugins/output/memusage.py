from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import options, plugin
from flexget.event import event
from flexget.logger import console

try:
    from guppy import hpy
except ImportError:
    # this will leave the plugin unloaded
    raise plugin.DependencyError(issued_by='memusage', missing='ext lib `guppy`', silent=True)

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

heapy = None


@event('manager.execute.started')
def on_exec_started(manager, options):
    if not options.mem_usage:
        return
    global heapy
    heapy = hpy()


@event('manager.execute.completed')
def on_exec_stopped(manager, options):
    if not options.mem_usage:
        return
    global heapy
    console('Calculating memory usage:')
    console(heapy.heap())
    console('-' * 79)
    console(heapy.heap().get_rp(40))
    heapy = None


@event('options.register')
def register_parser_arguments():
    options.get_parser('execute').add_argument('--mem-usage', action='store_true', dest='mem_usage', default=False,
                                               help='display memory usage debug information')
