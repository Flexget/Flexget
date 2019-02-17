from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import pytest


@pytest.mark.online
class TestRadarrListActions(object):
    config = """
        templates:
          global:
            disable: [seen]
        tasks:
          clear_and_add_to_radarr_list:
            list_clear:
              what:
                - radarr_list:
                    base_url: http://127.0.0.1
                    api_key: d2bcc5ec0c894b9587b6fbc3ff6ec11e
                    port: 7878
            mock:
              - { title: 'Despicable Me 2 (2013)', imdb_id: 'tt1690953', tmdb_id: 93456 }
              - { title: 'Sinister 2 (2015)', imdb_id: 'tt2752772', tmdb_id: 283445 }
              - { title: 'Crimson Peak (2015)', imdb_id: 'tt2554274', tmdb_id: 201085 }
              - { title: 'Deadpool (2016)', imdb_id: 'tt1431045', tmdb_id: 293660 }
            accept_all: yes
            list_add:
              - radarr_list:
                  base_url: http://127.0.0.1
                  api_key: d2bcc5ec0c894b9587b6fbc3ff6ec11e
                  port: 7878

          radarr_list_as_input_plugin:
            radarr_list:
              base_url: http://127.0.0.1
              api_key: d2bcc5ec0c894b9587b6fbc3ff6ec11e
              port: 7878
              include_data: True
            accept_all: yes

          remove_from_radarr_list:
            mock:
              - { title: "Ocean\'s Twelve (2004)", imdb_id: 'tt0349903', tmdb_id: 163 }
              - { title: 'Sinister 2 (2015)', imdb_id: 'tt2752772', tmdb_id: 283445 }
            accept_all: yes
            list_remove:
              - radarr_list:
                  base_url: http://127.0.0.1
                  api_key: d2bcc5ec0c894b9587b6fbc3ff6ec11e
                  port: 7878

          match_radarr_list:
            mock:
              - { title: 'Despicable.Me.2.2013.1080p.BluRay.x264-FlexGet', imdb_id: 'tt1690953', tmdb_id: 93456 }
              - { title: 'Sinister.2.2015.720p.BluRay.x264-FlexGet', imdb_id: 'tt2752772', tmdb_id: 283445 }
              - { title: 'Crimson.Peak.2015.720p.BluRay.x264-FlexGet', imdb_id: 'tt2554274', tmdb_id: 201085 }
              - { title: 'Deadpool.2016.1080p.BluRay.x264-FlexGet', imdb_id: 'tt1431045', tmdb_id: 293660 }
              - { title: 'Kung.Fu.Panda.3.2016.720p.BluRay.x264-FlexGet', imdb_id: 'tt2267968', tmdb_id: 140300 }
            list_match:
              from:
                - radarr_list:
                    base_url: http://127.0.0.1
                    api_key: d2bcc5ec0c894b9587b6fbc3ff6ec11e
                    port: 7878
    """

    # TODO: each action should be own test case
    def test_radarr_list_actions(self, execute_task):
        # Begin by clearing and then adding a bunch of movies
        task = execute_task('clear_and_add_to_radarr_list')

        # By using the list as the input we verify that the
        # movies added above is returned to us
        task = execute_task('radarr_list_as_input_plugin')
        assert task.find_entry(
            movie_name='Despicable Me 2'
        ), "movie should have been present in the list but it wasn't"
        assert task.find_entry(
            movie_name='Crimson Peak'
        ), "movie should have been present in the list but it wasn't"
        assert task.find_entry(
            movie_name='Deadpool'
        ), "movie should have been present in the list but it wasn't"
        assert task.find_entry(
            movie_name='Sinister 2'
        ), "movie should have been present in the list but it wasn't"

        # Now we will attempt to remove one existing (Sinister 2) and one
        # non-existing movie which should not affect anything at all
        task = execute_task('remove_from_radarr_list')

        # And to verify the list we fetch the list again
        # Sinister 2 should now be missing
        task = execute_task('radarr_list_as_input_plugin')
        assert task.find_entry(
            movie_name='Despicable Me 2'
        ), "movie should have been present in the list but it wasn't"
        assert task.find_entry(
            movie_name='Crimson Peak'
        ), "movie should have been present in the list but it wasn't"
        assert task.find_entry(
            movie_name='Deadpool'
        ), "movie should have been present in the list but it wasn't"
        assert not task.find_entry(
            movie_name='Sinister 2'
        ), "movie should not be present in the list but it was"

        # Now we will try to match a bunch of input entries with
        # the list. Two of the movies should not have been matched.
        task = execute_task('match_radarr_list')
        assert task.find_entry(
            'accepted', title='Despicable.Me.2.2013.1080p.BluRay.x264-FlexGet'
        ), "movie should have been matched but it wasn't"
        assert task.find_entry(
            'accepted', title='Crimson.Peak.2015.720p.BluRay.x264-FlexGet'
        ), "movie should have been matched but it wasn't"
        assert task.find_entry(
            'accepted', title='Deadpool.2016.1080p.BluRay.x264-FlexGet'
        ), "movie should have been matched but it wasn't"
        assert task.find_entry(
            'undecided', title='Sinister.2.2015.720p.BluRay.x264-FlexGet'
        ), "movie should not have been matched but it was"
        assert task.find_entry(
            'undecided', title='Kung.Fu.Panda.3.2016.720p.BluRay.x264-FlexGet'
        ), "movie should not have been matched but it was"

        # list_match should have removed all the matched movies
        # so no movies should remain
        task = execute_task('radarr_list_as_input_plugin')
        assert len(task.all_entries) == 0, "there should be no movies left in the list"
