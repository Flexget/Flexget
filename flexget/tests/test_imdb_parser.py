import pytest

from flexget.components.imdb.utils import ImdbParser


@pytest.mark.online
class TestImdbParser:
    def test_parsed_data(self):
        parser = ImdbParser()
        parser.parse('tt0114814')
        assert parser.actors == {
            'nm0000228': 'Kevin Spacey',
            'nm0000286': 'Stephen Baldwin',
            'nm0000321': 'Gabriel Byrne',
            'nm0000445': 'Dan Hedaya',
            'nm0000592': 'Pete Postlethwaite',
            'nm0000751': 'Suzy Amis',
            'nm0000860': 'Paul Bartel',
            'nm0001125': 'Benicio Del Toro',
            'nm0001590': 'Chazz Palminteri',
            'nm0001629': 'Kevin Pollak',
            'nm0002064': 'Giancarlo Esposito',
            'nm0107808': 'Carl Bressler',
            'nm0163988': 'Clark Gregg',
            'nm0198470': 'Ken Daly',
            'nm0261452': 'Christine Estabrook',
            'nm0402974': 'Morgan Hunter',
            'nm0790436': 'Jack Shearer',
            'nm0800339': 'Phillipe Simon',
        }, 'Actors not parsed correctly'
        assert parser.directors == {'nm0001741': 'Bryan Singer'}, 'Directors not parsed correctly'
        print(parser.genres)
        assert len(set(parser.genres).intersection(['crime', 'drama', 'mystery'])) == len(
            ['crime', 'drama', 'mystery']
        ), 'Genres not parsed correctly'
        assert parser.imdb_id == 'tt0114814', 'ID not parsed correctly'
        assert (
            len(set(parser.languages).intersection(['english', 'hungarian', 'spanish', 'french']))
            == 4
        ), 'Languages not parsed correctly'
        assert parser.mpaa_rating == 'R', 'Rating not parsed correctly'
        assert parser.name == 'The Usual Suspects', 'Name not parsed correctly'
        assert parser.photo, 'Photo not parsed correctly'
        assert parser.plot_outline == (
            'A sole survivor tells of the twisty events leading up to a horrific gun battle on a boat, which began '
            'when five criminals met at a seemingly random police lineup.'
        ), 'Plot outline not parsed correctly'
        assert 8.0 < parser.score < 9.0, 'Score not parsed correctly'
        assert parser.url == 'https://www.imdb.com/title/tt0114814/', 'URL not parsed correctly'
        assert 900000 < parser.votes < 1200000, 'Votes not parsed correctly'
        assert parser.year == 1995, 'Year not parsed correctly'
        expected_keywords = {
            'surprise ending',
            'criminal mastermind',
            'criminal',
            'suspect',
            'unreliable narrator',
        }
        assert len(expected_keywords.intersection(parser.plot_keywords)) == len(
            expected_keywords
        ), 'Parsed plot keywords missing items from the expected result'
        assert len(expected_keywords) == len(parser.plot_keywords), (
            'Parsed plot keyword count does not match expected.'
        )

    def test_no_plot(self):
        # Make sure parser doesn't crash for movies with no plot
        parser = ImdbParser()
        parser.parse('tt1300570')
        assert parser.name == 'Cuckold 1'
        # There is no plot
        assert not parser.plot_outline

    def test_no_year(self):
        # Make sure parser doesn't crash for movies with no year
        parser = ImdbParser()
        parser.parse('tt3303790')
        assert parser.name == 'Master of None'
        # There is no year
        assert not parser.year

    def test_plot_with_links(self):
        """Make sure plot doesn't terminate at the first link. GitHub #756."""
        parser = ImdbParser()
        parser.parse('tt2503944')
        assert parser.plot_outline == (
            'Adam Jones is a chef who destroyed his career with drugs and diva behavior. '
            'He cleans up and returns to London, determined to redeem himself by '
            'spearheading a top restaurant that can gain three Michelin stars.'
        )
