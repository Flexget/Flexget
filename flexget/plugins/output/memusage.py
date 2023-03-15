from loguru import logger

from flexget import options, plugin
from flexget.event import event
from flexget.terminal import console

try:
    from guppy import hpy
except ImportError:
    # this will leave the plugin unloaded
    raise plugin.DependencyError(issued_by='memusage', missing='guppy3', silent=True)

logger = logger.bind(name='mem_usage')

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


@event('manager.startup')
def on_manager_startup(manager):
    if not manager.options.mem_usage:
        return
    global heapy
    heapy = hpy()


@event('manager.shutdown')
def on_manager_shutdown(manager):
    if not manager.options.mem_usage:
        return

    try:
        import resource

        console(
            'Resource Module memory usage: %s (kb)'
            % resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        )
    except ImportError:
        console('Resource Module memory usage:')

    global heapy
    console('Heapy module calculating memory usage:')
    console(heapy.heap())
    console('-' * 79)
    console('Heapy module calculating report (this may take a while):')
    console(heapy.heap().get_rp(40))
    heapy = None


@event('options.register')
def register_parser_arguments():
    options.get_parser().add_argument(
        '--mem-usage',
        action='store_true',
        dest='mem_usage',
        default=False,
        help='display memory usage debug information',
    )
