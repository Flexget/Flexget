from __future__ import unicode_literals, division, absolute_import
import re
from argparse import _VersionAction

import flexget
from flexget.utils import requests
from flexget.plugin import register_parser_option


class CheckVersion(_VersionAction):
    def __call__(self, parser, namespace, values, option_string=None):
        messages = []
        try:
            page = requests.get('http://download.flexget.com')
        except requests.RequestException:
            messages.append('Error getting latest version number from download.flexget.com')
        else:
            ver = re.search(r'FlexGet-([\d\.]*)\.tar\.gz', page.text).group(1)
            if flexget.__version__ == ver:
                messages.append('You are on the latest version. (%s)' % ver)
            else:
                messages.append('You are on: %s' % flexget.__version__)
                messages.append('Latest release: %s' % ver)
        parser.exit(message='\n'.join(messages))

register_parser_option('--check-version', action=CheckVersion, help='Check for latest version.')