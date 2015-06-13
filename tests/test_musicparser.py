# -*- coding: utf8 -*-
from __future__ import unicode_literals, division, absolute_import
from flexget.plugins.parsers.music.parser_guessit_music import ParserGuessitMusic
import logging

log = logging.getLogger('test.music_parser')

checks = [{
              'raw': u'Betty Bonifassi 2014 [320 kpbs]',
              'year': 2014,
              'audioBitRate': '320kbps',
          }, {
              'raw': u'Lartiste Fenomeno',
          }, {
              'raw': u'[Electro/World]SKIP&DIE - Cosmic Serpents [320kbps]-megade',
              'artist': u'SKIP&DIE',
              'title': u'Cosmic Serpents',
              'audioBitRate': '320kbps',
          }, {
              'raw': u'(GFunk) Westpresentin - West In Peace Compilation 1997 ( Flac) R.G.',
              'artist': u'Westpresentin',
              'title': u'West In Peace',
              'year': 1997,
              'audioCodec': 'FLAC',
          }, {
              'raw': u'[1001 albums n°199] - Traffic - John Barleycorn Must Die [1970] [FLAC-16]',
              'artist': u'Traffic',
              'title': u'John Barleycorn Must Die',
              'year': 1970,
              'audioCodec': 'FLAC',
          }, {
              'raw': u'(Reggae 320 kbps) SELECTEUR OCTA™ - Mixtape Avril 2015',
              'year': 2015,
              'audioBitRate': '320kbps',
          }, {
              'raw': u'(GFunk) Lil Half Dead - Steel On The Mission 1996 (Flac) R.G.',
              'artist': u'Lil Half Dead',
              'title': u'Steel On The Mission',
              'year': 1996,
              'audioCodec': 'FLAC',
          }, {
              'raw': u'FUTURE TRANCE RAVE CLASSICS MP3 256Kbps 07/14',
              'audioCodec': 'MP3',
              'audioBitRate': '256kbps',
          }, {
              'raw': u'[Pop,Chanson] Le Noiseur - Du Bout des Lèvres (2015) Mp3-320',
              'artist': u'Le Noiseur',
              'title': u'Du Bout des Lèvres',
              'year': 2015,
              'audioCodec': 'MP3',
              'audioBitRate': '320kbps',
          }, {
              'raw': u'Human - Three Days Grace - 2015 - MP3 320',
              'artist': u'Human',
              'title': u'Three Days Grace',
              'year': 2015,
              'audioCodec': 'MP3',
              'audioBitRate': '320kbps',
          }, {
              'raw': u'Kaaris - Le Bruit De Mon Ame',
              'artist': u'Kaaris',
              'title': u'Le Bruit De Mon Ame',
          }, {
              'raw': u'[1001 albums n°751] - Orbital - Orbital 2 [1993] [FLAC-16]',
              'artist': u'Orbital',
              'title': u'Orbital 2',
              'year': 1993,
              'audioCodec': 'FLAC',
          }, {
              'raw': u'Tubes Télé & Génériques Dessins Animés Années 80 ',
          }, {
              'raw': u'Nirvana - Nevermind (1991) MP3 128 Kbits/s',
              'artist': u'Nirvana',
              'title': u'Nevermind',
              'year': 1991,
              'audioCodec': 'MP3',
              'audioBitRate': '128kbps',
          }, {
              'raw': u'VA - NRJ Spring Hits 2015 [CdRip - MP3 - 320kbps]',
              'artist': u'VA',
              'title': u'NRJ Spring Hits',
              'year': 2015,
              'audioCodec': 'MP3',
              'audioBitRate': '320kbps',
          }, {
              'raw': u'qubisme 2294 - em:t Rec. [Ambient - Mp3 @2300 Kbps]',
              'artist': u'qubisme 2294',
              'title': u'em:t Rec.',
              'audioCodec': 'MP3',
          }, {
              'raw': u'[Symphonic Death Metal] Everlasting Dawn - Seduction Passion Death - 2014 - MP3 - 320kbps',
              'artist': u'Everlasting Dawn',
              'title': u'Seduction Passion Death',
              'year': 2014,
              'audioCodec': 'MP3',
              'audioBitRate': '320kbps',
          }, {
              'raw': u'Eric Johnson - Europe Live - 2014 [flac]',
              'artist': u'Eric Johnson',
              'title': u'Europe Live',
              'year': 2014,
              'audioCodec': 'FLAC',
          }, {
              'raw': u'Thin Lizzy - Thunder & Lightning 1983 (Deluxe Edition 2013) (MP3 320 Kbps) hard rock ',
              'artist': u'Thin Lizzy',
              'title': u'Thunder & Lightning',
              'audioCodec': 'MP3',
              'audioBitRate': '320kbps',
          }, {
              'raw': u'[Punk-Rock] Pignoise - Esto No Es Un Disco De Punk [192 Kbps]',
              'artist': u'Pignoise',
              'title': u'Esto No Es Un Disco De Punk',
              'audioBitRate': '192kbps',
          }, {
              'raw': u'Elliott Murphy  & The Normandy All Stars - Live at New Morning 2010 2cd (flac) folk rock',
              'artist': u'Elliott Murphy  & The Normandy All Stars',
              'title': u'Live at New Morning',
              'year': 2010,
              'audioCodec': 'FLAC',
          }, {
              'raw': u'Black Violin - Black Violin - MP3 - 192kbps',
              'artist': u'Black Violin',
              'title': u'Black Violin',
              'audioCodec': 'MP3',
              'audioBitRate': '192kbps',
          }, {
              'raw': u'Chinese Man - Sho-Bro (2015) FLAC',
              'artist': u'Chinese Man',
              'title': u'Sho-Bro',
              'year': 2015,
              'audioCodec': 'FLAC',
          }, {
              'raw': u'Blitz the Ambassador - Afropolitan Dreams - mp3 [320Kbps]',
              'artist': u'Blitz the Ambassador',
              'title': u'Afropolitan Dreams',
              'audioCodec': 'MP3',
              'audioBitRate': '320kbps',
          }, {
              'raw': u'[1001 albums n°583] - Anita Baker - Rapture [1986] [FLAC-16]',
              'artist': u'Anita Baker',
              'title': u'Rapture',
              'year': 1986,
              'audioCodec': 'FLAC',
          }, {
              'raw': u'VILLAGE PEOPLE - DISCO COLLECTION (2002)[320 KBPS]',
              'artist': u'VILLAGE PEOPLE',
              'title': u'DISCO',
              'year': 2002,
              'audioBitRate': '320kbps',
          }, {
              'raw': u'Thin Lizzy - Thunder And Lightning (Deluxe Edition) 1983 (2013) (flac) hard rock',
              'artist': u'Thin Lizzy',
              'title': u'Thunder And Lightning',
              'audioCodec': 'FLAC',
          }, {
              'raw': u'Va Nrj Spring 2015 [MP3.320 kbps]',
              'year': 2015,
              'audioCodec': 'MP3',
              'audioBitRate': '320kbps',
          }, {
              'raw': u'A Life Divided  - The Great Escape (Winter Edition) - 2013 (mp3 320Kps)',
              'artist': u'A Life Divided ',
              'title': u'The Great Escape',
              'year': 2013,
              'audioCodec': 'MP3',
              'audioBitRate': '320kbps',
          }, {
              'raw': u'Apoplexy infection [death metal] Mp3',
              'audioCodec': 'MP3',
          }, {
              'raw': u'Evan band  [folk/rock] 210kbps',
              'audioBitRate': '210kbps',
          }, {
              'raw': u'Gary Moore - Close As You Get (2007) [Mp3-320kbps]',
              'artist': u'Gary Moore',
              'title': u'Close As You Get',
              'year': 2007,
              'audioCodec': 'MP3',
              'audioBitRate': '320kbps',
          }, {
              'raw': u'Louis-Jean Cormier - Les grandes artères - 2015 [320Kbps]',
              'artist': u'Louis-Jean Cormier',
              'title': u'Les grandes artères',
              'year': 2015,
              'audioBitRate': '320kbps',
          }, {
              'raw': u'CERONNE - DISCO COLLECTION (2002)[320 KBPS]',
              'artist': u'CERONNE',
              'title': u'DISCO',
              'year': 2002,
              'audioBitRate': '320kbps',
          }, {
              'raw': u'Ariane Moffatt - 22h22 (2015) [320Kbps]',
              'artist': u'Ariane Moffatt',
              'title': u'22h22',
              'year': 2015,
              'audioBitRate': '320kbps',
          }, {
              'raw': u'[Punk] Poison idea - Latest will and testament - 2006 [FLAC]',
              'artist': u'Poison idea',
              'title': u'Latest will and testament',
              'year': 2006,
              'audioCodec': 'FLAC',
          }, {
              'raw': u'Abramelin [death metal] Mp3',
              'audioCodec': 'MP3',
          }, {
              'raw': u'Vitaa - Celle Que Je Vois - 320 Kbps - MP3 - 2009',
              'artist': u'Vitaa',
              'title': u'Celle Que Je Vois',
              'year': 2009,
              'audioCodec': 'MP3',
              'audioBitRate': '320kbps',
          }, {
              'raw': u'Ol Kainry - Iron Mic 2.0 (2010) [2 CD]',
              'artist': u'Ol Kainry',
              'title': u'Iron Mic',
              'year': 2010,
          }, {
              'raw': u'Mallory Knox  Signals 2013 Rock MP3 320kbps',
              'year': 2013,
              'audioCodec': 'MP3',
              'audioBitRate': '320kbps',
          }, {
              'raw': u'[1001 albums n°806] - Goldie - Timeless [1995] [FLAC-16]',
              'artist': u'Goldie',
              'title': u'Timeless',
              'year': 1995,
              'audioCodec': 'FLAC',
          }, {
              'raw': u'Mary Komasa - Mary Komasa - 320 Kbps - MP3 - 2015',
              'artist': u'Mary Komasa',
              'title': u'Mary Komasa',
              'year': 2015,
              'audioCodec': 'MP3',
              'audioBitRate': '320kbps',
          }, {
              'raw': u'[MP3 320] Godspeed you! Black emperor - Asunder, Sweet and Other Distress ',
              'artist': u'Godspeed you! Black emperor',
              'title': u'Asunder, Sweet and Other Distress',
              'audioCodec': 'MP3',
              'audioBitRate': '320kbps',
          }, {
              'raw': u'[FLAC] Godspeed you! Black emperor - Asunder, Sweet and Other Distress ',
              'artist': u'Godspeed you! Black emperor',
              'title': u'Asunder, Sweet and Other Distress',
              'audioCodec': 'FLAC',
          }, {
              'raw': u'Luciole - Une - 320 Kbps - MP3 - 2015',
              'artist': u'Luciole',
              'title': u'Une',
              'year': 2015,
              'audioCodec': 'MP3',
              'audioBitRate': '320kbps',
          }, {
              'raw': u'Dead infection start human slaughter death metal',
          }, {
              'raw': u'em:t 2295 - em:t Rec. [Ambient - Mp3 @320 Kbps]',
              'artist': u'em:t 2295',
              'title': u'em:t Rec.',
              'audioCodec': 'MP3',
              'audioBitRate': '320kbps',
          }, {
              'raw': u'[1001 albums n°555] - Suzanne Vega - Suzanne Vega [1985] [FLAC-16]',
              'artist': u'Suzanne Vega',
              'title': u'Suzanne Vega',
              'year': 1985,
              'audioCodec': 'FLAC',
          }, {
              'raw': u'Hollywood Undead - Day Of The Dead Deluxe (2015) [MP3 320kbit/s]',
              'artist': u'Hollywood Undead',
              'title': u'Day Of The Dead',
              'year': 2015,
              'audioCodec': 'MP3',
              'audioBitRate': '320kbps',
          }, {
              'raw': u'[1001 albums n°696] - Public Enemy - Apocalypse \'91 \' The Enemy Strikes Black [1991] [FLAC-16]',
              'artist': u'Public Enemy',
              'title': u'Apocalypse \'91 \' The Enemy Strikes Black',
              'year': 1991,
              'audioCodec': 'FLAC'
          }]


class TestMusicParser(object):
    """
    I assume that a parser cannot manage all situations so I set a tolerance limit (5%) of
    parse error against a human parsing. The test will fail if failures exceed this limit.
    """
    def __init__(self):
        self.parser = ParserGuessitMusic()
        self.error_margin = 0.05
        self.success = 0
        self.fails = 0

    def check_entry(self, parsed_entry, expected_dict, assertor):
        """
        @type parsed_entry: flexget.plugins.parsers.parser_common.ParsedTitledAudio
        @type expected_dict: dict[str,str]
        """
        if expected_dict.get('artist') is not None:
            assertor(parsed_entry.artist, expected_dict.get('artist'))
        if expected_dict.get('title') is not None:
            assertor(parsed_entry.title, expected_dict.get('title'))
        if expected_dict.get('year') is not None:
            assertor(parsed_entry.year, expected_dict.get('year'))
        quality = parsed_entry.quality
        """@type : flexget.plugins.parsers.parser_common.ParsedAudioQuality"""

        if expected_dict.get('audioCodec') is not None:
            assertor(quality.audio_codec, expected_dict.get('audioCodec'))
        if expected_dict.get('audioBitRate') is not None:
            assertor(quality.audio_bit_rate, expected_dict.get('audioBitRate'))

    def permissive_assertor(self, actual, expected):
        is_success = actual == expected
        if is_success:
            self.success += 1
        else:
            self.fails += 1
            log.warning("Parsed '%s' instead of '%s'." % (actual, expected))

    def strict_assertor(self, actual, expected):
        assert actual == expected, "Parsed '%s' instead of '%s'." % (actual, expected)

    def test_parser(self):
        for check in checks:
            challenger = self.parser.parse_music(check['raw'])
            self.check_entry(challenger, check, self.permissive_assertor)

        error_rating = self.fails / (self.fails + self.success)
        assert error_rating < self.error_margin, \
            "Too much parse error ({0:.1%} > {1:.1%})".format(error_rating, self.error_margin)

        if self.fails > 0:
            log.info("{0:} faillure(s) on {1:} tests but test pass ({2:.1%} < {3:.1%})"
                     .format(self.fails, self.fails + self.success, error_rating, self.error_margin))
