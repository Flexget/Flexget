from flexget.components.imdb.imdb_watchlist import ImdbWatchlist

# Minimal fixture matching IMDB's advancedTitleSearch GraphQL node shape
# (mainColumnData.advancedTitleSearch.edges[].node.title)
TITLE_NODE = {
    'id': 'tt1663662',
    'titleText': {'text': 'Pacific Rim'},
    'titleType': {'id': 'movie'},
    'originalTitleText': {'text': 'Pacific Rim'},
    'releaseYear': {'year': 2013},
    'ratingsSummary': {'aggregateRating': 6.9, 'voteCount': 562211},
}


class TestImdbWatchlistParseEntry:
    def test_parse_entry(self):
        entry = ImdbWatchlist().parse_entry(TITLE_NODE, {})
        assert entry['imdb_id'] == 'tt1663662'
        assert entry['title'] == 'Pacific Rim (2013)'
        assert entry['movie_name'] == 'Pacific Rim'
        assert entry['movie_year'] == 2013
        assert entry['imdb_score'] == 6.9
        assert entry['imdb_votes'] == 562211
        assert entry['url'] == 'https://www.imdb.com/title/tt1663662/'

    def test_parse_entry_strip_dates(self):
        entry = ImdbWatchlist().parse_entry(TITLE_NODE, {'strip_dates': True})
        assert entry['title'] == 'Pacific Rim'
