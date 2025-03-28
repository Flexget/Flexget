import sys

from loguru import logger

from flexget import options
from flexget.event import event
from flexget.plugin import plugins
from flexget.terminal import console

logger = logger.bind(name='doc')


def trim(docstring):
    if not docstring:
        return ''
    # Convert tabs to spaces (following the normal Python rules)
    # and split into a list of lines:
    lines = docstring.expandtabs().splitlines()
    # Determine minimum indentation (first line doesn't count):
    indent = sys.maxsize
    for line in lines[1:]:
        stripped = line.lstrip()
        if stripped:
            indent = min(indent, len(line) - len(stripped))
    # Remove indentation (first line is special):
    trimmed = [lines[0].strip()]
    if indent < sys.maxsize:
        trimmed.extend([line[indent:].rstrip() for line in lines[1:]])
    # Strip off trailing and leading blank lines:
    while trimmed and not trimmed[-1]:
        trimmed.pop()
    while trimmed and not trimmed[0]:
        trimmed.pop(0)
    # Return a single string:
    return '\n'.join(trimmed)


def print_doc(manager, options):
    plugin_name = options.doc
    plugin = plugins.get(plugin_name, None)
    if plugin:
        if not plugin.instance.__doc__:
            console(f'Plugin {plugin_name} does not have documentation')
        else:
            console('')
            console(trim(plugin.instance.__doc__))
            console('')
    else:
        console(f'Could not find plugin {plugin_name}')


@event('options.register')
def register_parser_arguments():
    parser = options.register_command('doc', print_doc, help='display plugin documentation')
    parser.add_argument('doc', metavar='<plugin name>', help='name of plugin to show docs for')
