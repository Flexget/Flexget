import pytest

from flexget.components.managed_lists.lists.radarr_list import RadarrAPIService

RADARR_API_KEY = '65e246ce581a426781e1a8645f0a1f2c'
RADARR_BASE_URL = 'http://127.0.0.1'
RADARR_PORT = 7878


# Load up a radarr container and put VCR in record mode to record.
# NOTE: You'll need to reset radarr during runs otherwise the tags generated will have a different id. You'll also need to setup a root folder
# docker run -d --name=radarr-tmp -p 7878:7878 linuxserver/radarr:nightly
@pytest.mark.online
class TestRadarrListActions:
    config = f"""
        templates:
          global:
            disable: [seen]
        tasks:
          clear_and_add_to_radarr_list:
            list_clear:
              what:
                - radarr_list:
                    base_url: {RADARR_BASE_URL}
                    api_key: {RADARR_API_KEY}
                    port: {RADARR_PORT}
            mock:
              - {{ title: 'Despicable Me 2 (2013)', imdb_id: 'tt1690953', tmdb_id: 93456 }}
              - {{ title: 'Sinister 2 (2015)', imdb_id: 'tt2752772', tmdb_id: 283445 }}
              - {{ title: 'Crimson Peak (2015)', imdb_id: 'tt2554274', tmdb_id: 201085 }}
              - {{ title: 'Deadpool (2016)', imdb_id: 'tt1431045', tmdb_id: 293660 }}
            accept_all: yes
            list_add:
              - radarr_list:
                  base_url: {RADARR_BASE_URL}
                  api_key: {RADARR_API_KEY}
                  port: {RADARR_PORT}

          clear_and_add_to_radarr_with_tags:
            list_clear:
              what:
                - radarr_list:
                    base_url: {RADARR_BASE_URL}
                    api_key: {RADARR_API_KEY}
                    port: {RADARR_PORT}
            mock:
              - {{ title: 'Deadpool (2016)', imdb_id: 'tt1431045', tmdb_id: 293660 }}
            accept_all: yes
            list_add:
              - radarr_list:
                  base_url: {RADARR_BASE_URL}
                  api_key: {RADARR_API_KEY}
                  port: {RADARR_PORT}
                  tags: ["movies", "othertag"]

          radarr_list_as_input_plugin:
            radarr_list:
              base_url: {RADARR_BASE_URL}
              api_key: {RADARR_API_KEY}
              port: {RADARR_PORT}
              include_data: True
            accept_all: yes

          remove_from_radarr_list:
            mock:
              - {{ title: "Ocean\'s Twelve (2004)", imdb_id: 'tt0349903', tmdb_id: 163 }}
              - {{ title: 'Sinister 2 (2015)', imdb_id: 'tt2752772', tmdb_id: 283445 }}
            accept_all: yes
            list_remove:
              - radarr_list:
                  base_url: {RADARR_BASE_URL}
                  api_key: {RADARR_API_KEY}
                  port: {RADARR_PORT}

          match_radarr_list:
            mock:
              - {{ title: 'Despicable.Me.2.2013.1080p.BluRay.x264-FlexGet', imdb_id: 'tt1690953', tmdb_id: 93456 }}
              - {{ title: 'Sinister.2.2015.720p.BluRay.x264-FlexGet', imdb_id: 'tt2752772', tmdb_id: 283445 }}
              - {{ title: 'Crimson.Peak.2015.720p.BluRay.x264-FlexGet', imdb_id: 'tt2554274', tmdb_id: 201085 }}
              - {{ title: 'Deadpool.2016.1080p.BluRay.x264-FlexGet', imdb_id: 'tt1431045', tmdb_id: 293660 }}
              - {{ title: 'Kung.Fu.Panda.3.2016.720p.BluRay.x264-FlexGet', imdb_id: 'tt2267968', tmdb_id: 140300 }}
            list_match:
              from:
                - radarr_list:
                    base_url: {RADARR_BASE_URL}
                    api_key: {RADARR_API_KEY}
                    port: {RADARR_PORT}
    """

    def test_radarr_list_tags(self, execute_task, manager):
        radarr = RadarrAPIService(RADARR_API_KEY, RADARR_BASE_URL, RADARR_PORT)
        tag_by_id = radarr.add_tag('tag_by_id')["id"]
        manager.config['tasks']['clear_and_add_to_radarr_with_tags']['list_add'][0]['radarr_list'][
            'tags'
        ].append(tag_by_id)

        execute_task('clear_and_add_to_radarr_with_tags')
        tags = {t["label"].lower(): t["id"] for t in radarr.get_tags()}
        for movie in radarr.get_movies():
            assert sorted(movie['tags']) == sorted(
                [tag_by_id, tags.get("movies"), tags.get("othertag")]
            )

    # TODO: each action should be own test case
    def test_radarr_list_actions(self, execute_task):
        # Begin by clearing and then adding a bunch of movies
        task = execute_task('clear_and_add_to_radarr_list')

        # By using the list as the input we verify that the
        # movies added above is returned to us
        task = execute_task('radarr_list_as_input_plugin')
        assert task.find_entry(movie_name='Despicable Me 2'), (
            "movie should have been present in the list but it wasn't"
        )
        assert task.find_entry(movie_name='Crimson Peak'), (
            "movie should have been present in the list but it wasn't"
        )
        assert task.find_entry(movie_name='Deadpool'), (
            "movie should have been present in the list but it wasn't"
        )
        assert task.find_entry(movie_name='Sinister 2'), (
            "movie should have been present in the list but it wasn't"
        )

        # Now we will attempt to remove one existing (Sinister 2) and one
        # non-existing movie which should not affect anything at all
        task = execute_task('remove_from_radarr_list')

        # And to verify the list we fetch the list again
        # Sinister 2 should now be missing
        task = execute_task('radarr_list_as_input_plugin')
        assert task.find_entry(movie_name='Despicable Me 2'), (
            "movie should have been present in the list but it wasn't"
        )
        assert task.find_entry(movie_name='Crimson Peak'), (
            "movie should have been present in the list but it wasn't"
        )
        assert task.find_entry(movie_name='Deadpool'), (
            "movie should have been present in the list but it wasn't"
        )
        assert not task.find_entry(movie_name='Sinister 2'), (
            "movie should not be present in the list but it was"
        )

        # Now we will try to match a bunch of input entries with
        # the list. Two of the movies should not have been matched.
        task = execute_task('match_radarr_list')
        assert task.find_entry(
            'accepted', title='Despicable.Me.2.2013.1080p.BluRay.x264-FlexGet'
        ), "movie should have been matched but it wasn't"
        assert task.find_entry('accepted', title='Crimson.Peak.2015.720p.BluRay.x264-FlexGet'), (
            "movie should have been matched but it wasn't"
        )
        assert task.find_entry('accepted', title='Deadpool.2016.1080p.BluRay.x264-FlexGet'), (
            "movie should have been matched but it wasn't"
        )
        assert task.find_entry('undecided', title='Sinister.2.2015.720p.BluRay.x264-FlexGet'), (
            "movie should not have been matched but it was"
        )
        assert task.find_entry(
            'undecided', title='Kung.Fu.Panda.3.2016.720p.BluRay.x264-FlexGet'
        ), "movie should not have been matched but it was"

        # list_match should have removed all the matched movies
        # so no movies should remain
        task = execute_task('radarr_list_as_input_plugin')
        assert len(task.all_entries) == 0, "there should be no movies left in the list"
