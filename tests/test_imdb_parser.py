import pytest

from flexget.components.imdb.utils import ImdbParser


@pytest.mark.online
class TestImdbParser:
    def test_parsed_data(self):
        parser = ImdbParser()
        parser.parse('tt0114814')
        expected_actors = {
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
        }
        for aid, aname in expected_actors.items():
            assert parser.actors.get(aid) == aname, f'Missing or wrong actor {aid}'
        assert len(parser.actors) >= len(expected_actors), 'Expected at least the top-billed cast'
        assert parser.directors == {'nm0001741': 'Bryan Singer'}, 'Directors not parsed correctly'
        print(parser.genres)
        assert len(set(parser.genres).intersection(['crime', 'drama', 'mystery'])) == len([
            'crime',
            'drama',
            'mystery',
        ]), 'Genres not parsed correctly'
        assert parser.imdb_id == 'tt0114814', 'ID not parsed correctly'
        assert (
            len(set(parser.languages).intersection(['english', 'hungarian', 'spanish', 'french']))
            == 4
        ), 'Languages not parsed correctly'
        assert parser.mpaa_rating == 'R', 'Rating not parsed correctly'
        assert parser.name == 'The Usual Suspects', 'Name not parsed correctly'
        assert parser.photo, 'Photo not parsed correctly'
        assert parser.plot_outline == (
            'The sole survivor of a pier shoot-out tells the story of how a notorious criminal '
            'influenced the events that began with five criminals meeting in a seemingly random '
            'police lineup.'
        ), 'Plot outline not parsed correctly'
        assert 8.0 < parser.score < 9.0, 'Score not parsed correctly'
        assert parser.url == 'https://www.imdb.com/title/tt0114814/', 'URL not parsed correctly'
        assert 800000 < parser.votes < 2000000, 'Votes not parsed correctly'
        assert parser.year == 1995, 'Year not parsed correctly'
        expected_keywords = {
            'surprise ending',
            'criminal mastermind',
            'criminal',
            'suspect',
            'unreliable narrator',
        }
        missing_kw = expected_keywords - set(parser.plot_keywords)
        assert not missing_kw, f'Parsed plot keywords missing: {missing_kw}'

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
        outline = parser.plot_outline or ''
        msg = f'Expected in plot, got: {outline[:120]!r}...'
        assert 'London' in outline, msg
        assert 'chef' in outline.lower(), msg
