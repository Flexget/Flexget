from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event

log = logging.getLogger('torznab')


class Torznab(object):
    """Torznab search plugin

    Handles searching for tv shows and movies, with fallback to simple query strings if these are not available.
    """

    @property
    def schema(self):
        """The schema of the plugin"""
        schema = {
            'type': 'object',
            'properties': {
                'apikey': {'type': 'string'},
                'categories': {'type': 'array', 'items': {'type': 'integer'}, 'default': []},
                'searcher': {'type': 'string', 'enum': ['movie', 'tv', 'tvsearch', 'search'], 'default': 'search'},
                'website': {'type': 'string', 'format': 'url'}
            },
            'required': ['website', 'apikey'],
            'additionalProperties': False
        }
        return schema

    def search(self, task, entry, config=None):
        """Search interface"""
        return []


@event('plugin.register')
def register_plugin():
    plugin.register(Torznab, 'torznab', api_ver=2, interfaces=['search'])
