import pytest


@pytest.mark.online
class TestAnimeRelations:
    config = """
        tasks:
          test:
            anime_relations: true
            accept_all: true
            mock:
              - {title: 'AniDB', anidb_id: 14792}
              - {title: 'Anilist', al_id: 108632}
              - {title: 'AnimeCountdown', animecountdown_id: 1063491}
              - {title: 'AnimePlanet', animeplanet_id: 're-zero-starting-life-in-another-world-season-2'}
              - {title: 'AniSearch', anisearch_id: 14302}
              - {title: 'AnimeNewsNetwork', ann_id: 22005}
              - {title: 'IMDB', imdb_id: 'tt5607616'}
              - {title: 'Kitsu', kitsu_id: 42198}
              - {title: 'LiveChart', livechart_id: 9387}
              - {title: 'MyAnimeList', mal_id: 39587}
              - {title: 'Simkl', simkl_id: 1063491}
              - {title: 'TMDB', tmdb_id: 65942}
              - {title: 'TVDB', tvdb_id: 305089, series_season: 2}
    """

    def test_anime_relations(self, request, execute_task):
        task = execute_task('test', options={'nocache': True})
        valid_entries = [
            ['AniDB', 'anidb_id', 14792],
            ['Anilist', 'al_id', 108632],
            ['AnimeCountdown', 'animecountdown_id', 1063491],
            ['AnimePlanet', 'animeplanet_id', 're-zero-starting-life-in-another-world-season-2'],
            ['AniSearch', 'anisearch_id', 14302],
            ['AnimeNewsNetwork', 'ann_id', 22005],
            ['Kitsu', 'kitsu_id', 42198],
            ['LiveChart', 'livechart_id', 9387],
            ['MyAnimeList', 'mal_id', 39587],
            ['Simkl', 'simkl_id', 1063491],
        ]
        #  Shouldn't test for TMDB, TVDB or IMDB since they are not unique.
        #  TVDB has the season to narrow it down but it's a split-cour so there's an offset
        extra_fields = [
            ('imdb_id', 'tt5607616'),
            ('tmdb_id', 65942),
            ('tmdb_season', 1),
            ('tmdb_offset', 26),
            ('tvdb_id', 305089),
            ('tvdb_season', 2),
            ('tvdb_offset', None),
        ]

        def check_fields(entry):
            for fields in valid_entries:
                _name, field, value = fields
                try:
                    result = entry[field]
                except KeyError:
                    result = None
                assert result == value, (
                    f'Entry {entry["title"]} should have field {field} set to {value} instead of {result}'
                )

        for valid in valid_entries:
            entry = task.find_entry(title=valid[0])
            if entry is None:
                raise AssertionError(f'Could not find {valid[0]}')
            check_fields(entry)
            for field, value in extra_fields:
                try:
                    result = entry[field]
                except KeyError:
                    result = None
                assert result == value, (
                    f'Entry {valid[0]} should have field {field} set to {value} instead of {result}'
                )
