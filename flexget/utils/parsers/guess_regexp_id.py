from __future__ import absolute_import, division, print_function, unicode_literals

from guessit.plugins.transformers import Transformer
from guessit.matcher import GuessFinder
from guessit.containers import PropertiesContainer


class GuessRegexpId(Transformer):
    def __init__(self):
        Transformer.__init__(self, 21)

    def supported_properties(self):
        return ['regexpId']

    def guess_regexps_id(self, string, node=None, options=None):
        container = PropertiesContainer(enhance=False, canonical_from_pattern=False)
        for regexp in options.get("id_regexps"):
            container.register_property('regexpId', regexp, confidence=1.0)
        found = container.find_properties(string, node, options)
        return container.as_guess(found, string)

    def should_process(self, mtree, options=None):
        return options and options.get("id_regexps")

    def process(self, mtree, options=None):
        GuessFinder(self.guess_regexps_id, None, self.log, options).process_nodes(mtree.unidentified_leaves())