import sys
from pathlib import Path

import flexget
from flexget import options
from flexget.event import event
from flexget.terminal import console
from flexget.utils.tools import io_encoding


def print_debug_info(manager, options):
    install_location = Path(__file__).absolute().parent.parent.parent
    console(f'FlexGet Version: {flexget.__version__}')
    console(f'Install location: {install_location}')
    console(f'Config location: {manager.config_path}')
    console('Python version: {}.{}.{}'.format(*sys.version_info[:3]))
    console(f'Detected IO encoding: {io_encoding}')


@event('options.register')
def register_parser_arguments():
    options.register_command(
        'debug-info', print_debug_info, help='display useful info for debugging'
    )
