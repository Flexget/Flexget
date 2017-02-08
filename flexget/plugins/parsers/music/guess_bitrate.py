import re

from guessit.plugins.transformers import Transformer
from guessit.matcher import GuessFinder

common_bitrates = [32, 64, 96, 112, 128, 160, 192, 224, 256, 320]


class GuessBitrate(Transformer):
    def __init__(self):
        Transformer.__init__(self, 40)
        """
        The strict mode need a bitrate writed with its unit (k, kbps, ...)
        at any circumstance. Permissive move (aka non strict mode) dont
        need bitrate unit but can find only a set of common bitrate
        values (128kpbs, 320kbps etc)
        """
        self.strict_mode = False

    def supported_properties(self):
        return ['audioBitRate']

    def guess_bitrate(self, string, node=None, options=None):
        match = re.search(r'(?i)(?:[^0-9]|\A)(([0-9]{2,3})[\._\- ]?(k(?:bps|bits?(\\s)?)?)?)(?:\Z|[^0-9])', string)
        if match:
            bitrate = int(match.group(2))
            explicit_unit = (match.group(3) is not None)

            # see: self.strict_mode
            if explicit_unit or ((bitrate in common_bitrates) and not self.strict_mode):
                return {'audioBitRate': '%ikbps' % bitrate}, match.span(1)

        return None, None

    def second_pass_options(self, mtree, options=None):
        nodes = list(mtree.leaves_containing('audioBitRate'))
        if len(nodes) > 1:
            return {'skip_nodes': nodes[:len(nodes) - 1]}
        return None

    def process(self, mtree, options=None):
        GuessFinder(self.guess_bitrate, 1.0, self.log, options).process_nodes(mtree.unidentified_leaves())
