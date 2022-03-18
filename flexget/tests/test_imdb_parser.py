import pytest

from flexget.components.imdb.utils import ImdbParser


@pytest.mark.online
class TestImdbParser:
    def test_parsed_data(self):
        parser = ImdbParser()
        parser.parse('tt0114814')
        assert parser.actors == {
            'nm0000445': 'Dan Hedaya',
            'nm0000592': 'Pete Postlethwaite',
            'nm0000751': 'Suzy Amis',
            'nm0000860': 'Paul Bartel',
            'nm0001125': 'Benicio Del Toro',
            'nm0001629': 'Kevin Pollak',
            'nm0002064': 'Giancarlo Esposito',
            'nm0107808': 'Carl Bressler',
            'nm0163988': 'Clark Gregg',
            'nm0167342': 'Michelle Clunie',
            'nm0198470': 'Ken Daly',
            'nm0261452': 'Christine Estabrook',
            'nm0402974': 'Morgan Hunter',
            'nm0518385': 'Louis Lombardi',
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
            'Following a truck hijack in New York, five criminals are arrested and '
            'brought together for questioning. As none of them are guilty, they plan a '
            'revenge operation against the police. The operation goes well, but then the '
            'influence of a legendary mastermind criminal called Keyser Söze is felt. It '
            'becomes clear that each one of them has wronged Söze at some point and must '
            'pay back now. The payback job leaves 27 men dead in a boat explosion, but '
            'the real question arises now: Who actually is Keyser Söze?'
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
        assert len(expected_keywords) == len(
            parser.plot_keywords
        ), 'Parsed plot keyword count does not match expected.'

    def test_no_plot(self):
        # Make sure parser doesn't crash for movies with no plot
        parser = ImdbParser()
        parser.parse('tt1300562')
        assert parser.name == 'Adieu mères'
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
        """Make sure plot doesn't terminate at the first link. GitHub #756"""
        parser = ImdbParser()
        parser.parse('tt2503944')
        assert parser.plot_outline == (
            "Chef Adam Jones (Bradley Cooper) had it all - and lost it. A two-star Michelin "
            "rockstar with the bad habits to match, the former enfant terrible of the Paris "
            "restaurant scene did everything different every time out, and only ever cared "
            "about the thrill of creating explosions of taste. To land his own kitchen and "
            "that third elusive Michelin star though, he'll need the best of the best on "
            "his side, including the beautiful Helene (Sienna Miller)."
        )
