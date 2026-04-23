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
              - {title: 'TVDB', tvdb_id: 305089}
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

        def check_fields(entry):
            for fields in valid_entries:
                name, field, value = fields
                assert entry[field] == value, (
                    f'Entry {name} should have field {field} set to {value}'
                )

        for valid in valid_entries:
            entry = task.find_entry(title=valid[0])
            if entry is None:
                raise AssertionError(f'Could not find {valid[0]}')
            check_fields(entry)

        #  The plugin should not populate based on these fields since they are not unique
        invalid_entries = ['IMDB', 'TMDB', 'TVDB']

        for name in invalid_entries:
            entry = task.find_entry(title=name)
            assert 'anidb_id' not in entry, f'Entry {name} should not have the anidb_id field'
