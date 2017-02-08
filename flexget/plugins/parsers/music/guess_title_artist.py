from __future__ import absolute_import, division, print_function, unicode_literals

import re

from guessit.plugins.transformers import Transformer
from guessit.matcher import GuessFinder


def find_title_artist_node(mtree):
    return None

class GuessMusicArtistAndTitle(Transformer):
    """Guess 'artist - title'"""

    def __init__(self):
        Transformer.__init__(self, -200)

    def supported_properties(self):
        return ['title', 'artist']

    def should_process(self, mtree, options=None):
        options = options or {}
        return not options.get('skip_title')

    def guess_artist_title(self, string, node=None, options=None):
        match = re.search(r'(- +)?([^ ].+) - (.+[^ \-])', string)
        if match:
            artist = match.group(2)
            title = match.group(3)
            result = {'artist': artist, 'title': title}, (match.span(0))
            return result

        return None, None

    def process(self, mtree, options=None):
        if 'title' in mtree.info:
            return
        leaves = []
        for leave in mtree.unidentified_leaves():
            leaves.append(leave)
        GuessFinder(self.guess_artist_title, 1.0, self.log, options).process_nodes(mtree.unidentified_leaves())