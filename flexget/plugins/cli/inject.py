import argparse
import random
import string

import yaml

from flexget import options
from flexget.entry import Entry
from flexget.event import event
from flexget.terminal import console
from flexget.utils import requests
from flexget.utils.requests import parse_header


@event('manager.subcommand.inject')
def do_cli(manager, options):
    # Determine if first positional argument is a URL or a title
    if not options.url and '://' in options.title:
        options.url = options.title
        options.title = None

    if options.url and not options.title:
        # Attempt to get a title from the URL response's headers
        try:
            value, params = parse_header(requests.head(options.url).headers['Content-Disposition'])
            options.title = params['filename']
        except KeyError:
            console("No title given, and couldn't get one from the URL's HTTP response. Aborting.")
            return

    entry = Entry(title=options.title)
    if options.url:
        entry['url'] = options.url
    else:
        entry['url'] = 'http://localhost/inject/{}'.format(
            ''.join(random.sample(string.ascii_letters + string.digits, 30))
        )
    if options.force:
        entry['immortal'] = True
    if options.accept:
        entry.accept(reason='accepted by CLI inject')
    if options.fields:
        for key, value in options.fields:
            entry[key] = value
    options.inject = [entry]
    manager.execute_command(options)


def key_equals_value(text):
    if '=' not in text:
        raise argparse.ArgumentTypeError('must be in the form: <field name>=<value>')
    key, value = text.split('=')
    return key, yaml.safe_load(value)


# Run after other plugins, so we can get all exec subcommand options
@event('options.register', priority=0)
def register_parser_arguments():
    exec_parser = options.get_parser('execute')
    inject_parser = options.register_command(
        'inject',
        do_cli,
        add_help=False,
        parents=[exec_parser],
        help='inject an entry from command line into tasks',
        usage='%(prog)s title/url [url] [--accept] [--force] '
        '[--fields NAME=VALUE [NAME=VALUE...]] [<execute arguments>]',
        epilog=(
            'If only a URL and no title is given, Flexget will attempt to '
            "find a title in the URL's response headers."
        ),
    )
    inject_group = inject_parser.add_argument_group('inject arguments')
    inject_group.add_argument(
        'title', metavar='title/url', help='title or url of the entry to inject'
    )
    inject_group.add_argument('url', nargs='?', help='url of the entry to inject')
    inject_group.add_argument(
        '--force', action='store_true', help='prevent any plugins from rejecting this entry'
    )
    inject_group.add_argument(
        '--accept', action='store_true', help='accept this entry immediately upon injection'
    )
    inject_group.add_argument('--fields', metavar='NAME=VALUE', nargs='+', type=key_equals_value)
    # Hack the title of the exec options a bit (would be 'optional arguments' otherwise)
    inject_parser._action_groups[1].title = 'execute arguments'
    # The exec arguments show first... unless we switch them
    inject_parser._action_groups.remove(inject_group)
    inject_parser._action_groups.insert(0, inject_group)
