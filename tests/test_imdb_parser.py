from __future__ import unicode_literals, division, absolute_import

from nose.plugins.attrib import attr

from flexget.utils.imdb import ImdbParser


class TestImdbParser(object):
    @attr(online=True)
    def test_parsed_data(self):
        parser = ImdbParser()
        parser.parse('tt0114814')
        assert parser.actors == {
            'nm0000592': 'Pete Postlethwaite',
            'nm0261452': 'Christine Estabrook',
            'nm0000751': 'Suzy Amis',
            'nm0000286': 'Stephen Baldwin',
            'nm0000445': 'Dan Hedaya',
            'nm0800339': 'Phillipe Simon',
            'nm0002064': 'Giancarlo Esposito',
            'nm0001590': 'Chazz Palminteri',
            'nm0000321': 'Gabriel Byrne',
            'nm0790436': 'Jack Shearer',
            'nm0000228': 'Kevin Spacey',
            'nm0001629': 'Kevin Pollak',
            'nm0107808': 'Carl Bressler',
            'nm0001125': 'Benicio Del Toro',
            'nm0000860': 'Paul Bartel'
        }, 'Actors not parsed correctly'
        assert parser.directors == {'nm0001741': 'Bryan Singer'}, 'Directors not parsed correctly'
        assert parser.genres == [u'crime', u'mystery', u'thriller'], 'Genres not parsed correctly'
        assert parser.imdb_id == 'tt0114814', 'ID not parsed correctly'
        assert parser.languages == ['english', 'hungarian', 'spanish', 'french'], 'Languages not parsed correctly'
        assert parser.mpaa_rating == 'R', 'Rating not parsed correctly'
        assert parser.name == 'The Usual Suspects', 'Name not parsed correctly'
        assert (parser.photo ==
                'http://ia.media-imdb.com/images/M/MV5BMzI1MjI5MDQyOV5BMl5BanBnXkFtZTcwNzE4Mjg3NA@@._V1_SX214_.jpg'
        ), 'Photo not parsed correctly'
        assert parser.plot_outline == (
            'Following a truck hijack in New York, five conmen are arrested and brought together for questioning. '
            'As none of them is guilty, they plan a revenge operation against the police. The operation goes well, '
            'but then the influence of a legendary mastermind criminal called Keyser S\xf6ze is felt. It becomes '
            'clear that each one of them has wronged S\xf6ze at some point and must pay back now. The payback job '
            'leaves 27 men dead in a boat explosion, but the real question arises now: Who actually is Keyser S\xf6ze?'
        ), 'Plot outline not parsed correctly'
        assert 8.0 < parser.score < 9.0, 'Score not parsed correctly'
        assert parser.url == 'http://www.imdb.com/title/tt0114814/', 'URL not parsed correctly'
        assert 400000 < parser.votes < 500000, 'Votes not parsed correctly'
        assert parser.year == 1995, 'Year not parsed correctly'

    @attr(online=True)
    def test_no_plot(self):
        # Make sure parser doesn't crash for movies with no plot
        parser = ImdbParser()
        parser.parse('tt0245062')
        assert parser.name == 'The Magnet'
        # There is no plot
        assert not parser.plot_outline
