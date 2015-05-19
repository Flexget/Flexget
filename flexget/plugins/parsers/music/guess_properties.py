from guessit.plugins.transformers import Transformer
from guessit.containers import PropertiesContainer, LeavesValidator, LeftValidator
from guessit.matcher import GuessFinder


class GuessProperties(Transformer):
    def __init__(self):
        Transformer.__init__(self, 35)
        self.container = PropertiesContainer()

        def register_property(propname, props, **kwargs):
            """props a dict of {value: [patterns]}"""
            for canonical_form, patterns in props.items():
                if isinstance(patterns, tuple):
                    patterns2, pattern_kwarg = patterns
                    if kwargs:
                        current_kwarg = dict(kwargs)
                        current_kwarg.update(pattern_kwarg)
                    else:
                        current_kwarg = dict(pattern_kwarg)
                    current_kwarg['canonical_form'] = canonical_form
                    self.container.register_property(propname, *patterns2, **current_kwarg)
                elif kwargs:
                    current_kwarg = dict(kwargs)
                    current_kwarg['canonical_form'] = canonical_form
                    self.container.register_property(propname, *patterns, **current_kwarg)
                else:
                    self.container.register_property(propname, *patterns, canonical_form=canonical_form)

        register_property('source', {
            'cdrip': ['cdrip', 'cd.rip']
        })

        # register_property('additional', {
        #     'deluxe': ['(?i)deluxe.edition', 'deluxe'],
        #     'collection': ['collection'],
        #     'discography': ['discography', 'discographie'],
        #     'compilation': ['compilation', 'compile'],
        #     'mixtape': ['mixtape'],
        #     'soundtrack': ['soundtrack', 'ost']
        #     'single': 'single'
        # })

        register_property('audioCodec', {
            'AAV': ['MP4', 'M4A', 'AAC'],
            'AC3': ['ac3'],
            'aif': ['aif'],
            'alac': ['alac'],
            'DSD': ['SACD', 'DSD'],
            'DTS': (['DTS'], {'validator': LeftValidator()}),
            'FLAC': (['FLAC'], {'validator': LeftValidator()}),
            'MP3': ['MP3', 'MPEG-3', 'MPEG3'],
            'vorbis': ['ogg', 'oga'],
            'monkey': ['ape'],
            'musepack': ['musepack', 'mp(eg)?(plus|\+)'],
            'wavpack': ['wavpack', 'wv'],
            'wma': ['wma']
        })

        self.container.register_property('audioProfile', 'HD', validator=LeavesValidator(lambdas=[lambda node: node.guess.get('audioCodec') == 'DTS']))
        self.container.register_property('audioProfile', 'HD-MA', canonical_form='HDMA', validator=LeavesValidator(lambdas=[lambda node: node.guess.get('audioCodec') == 'DTS']))
        self.container.register_property('audioProfile', 'HE', validator=LeavesValidator(lambdas=[lambda node: node.guess.get('audioCodec') == 'AAC']))
        self.container.register_property('audioProfile', 'LC', validator=LeavesValidator(lambdas=[lambda node: node.guess.get('audioCodec') == 'AAC']))
        self.container.register_property('audioProfile', 'HQ', validator=LeavesValidator(lambdas=[lambda node: node.guess.get('audioCodec') == 'AC3']))

        register_property('audioBitRateDistribution', {
            'abr': ['abr'],
            'cbr': ['cbr'],
            'vbr': ['vbr']
        })

        register_property('audioChannels', {
            '7.1': ['7[\W_]1', '7ch', '8ch'],
            '5.1': ['5[\W_]1', '5ch', '6ch'],
            '2.0': ['2[\W_]0', '2ch', 'stereo'],
            '1.0': ['1[\W_]0', '1ch', 'mono']
        })

    def guess_properties(self, string, node=None, options=None):
        found = self.container.find_properties(string, node, options)
        return self.container.as_guess(found, string)

    def supported_properties(self):
        return self.container.get_supported_properties()

    def process(self, mtree, options=None):
        GuessFinder(self.guess_properties, 1.0, self.log, options).process_nodes(mtree.unidentified_leaves())
