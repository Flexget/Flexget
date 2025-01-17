import pytest

from flexget.components.managed_lists.lists.sonarr_list import SonarrSet

SONARR_API_KEY = '7f0a2ce32a3e43c8a7389e9539c487b4'
SONARR_BASE_URL = 'http://127.0.0.1'
SONARRR_PORT = 8989


# Load up a sonarr container and put VCR in record mode to record.
# NOTE: You'll need to reset sonarr during runs otherwise the tags generated will have a different id. You'll also need to setup a root folder
# docker run -d --name=sonarr-tmp -p 8989:8989 linuxserver/sonarr:preview
@pytest.mark.online
class TestSonarrListActions:
    config = f"""
        templates:
          global:
            disable: [seen]
        tasks:
          clear_and_add_to_sonarr_list:
            list_clear:
              what:
                - sonarr_list:
                    base_url: {SONARR_BASE_URL}
                    api_key: {SONARR_API_KEY}
                    port: {SONARRR_PORT}
            mock:
              - {{ title: 'Breaking Bad', imdb_id: 'tt0903747', tvdb_id: 81189 }}
              - {{ title: 'The Walking Dead', imdb_id: 'tt1520211', tvdb_id: 153021 }}
              - {{ title: 'Game of Thrones', imdb_id: 'tt0944947', tvdb_id: 121361 }}
            accept_all: yes
            list_add:
              - sonarr_list:
                  base_url: {SONARR_BASE_URL}
                  api_key: {SONARR_API_KEY}
                  port: {SONARRR_PORT}

          clear_and_add_to_sonarr_with_tags:
            list_clear:
              what:
                - sonarr_list:
                    base_url: {SONARR_BASE_URL}
                    api_key: {SONARR_API_KEY}
                    port: {SONARRR_PORT}
            mock:
              - {{ title: 'Game of Thrones', imdb_id: 'tt0944947', tvdb_id: 121361 }}
            accept_all: yes
            list_add:
              - sonarr_list:
                  base_url: {SONARR_BASE_URL}
                  api_key: {SONARR_API_KEY}
                  port: {SONARRR_PORT}
                  tags: ["tv", "othertag"]

          sonarr_list_as_input_plugin:
            sonarr_list:
              base_url: {SONARR_BASE_URL}
              api_key: {SONARR_API_KEY}
              port: {SONARRR_PORT}
              include_data: True
            accept_all: yes

          remove_from_sonarr_list:
            mock:
              - {{ title: 'Breaking Bad', imdb_id: 'tt0903747', tvdb_id: 81189 }}
              - {{ title: 'The Simpsons', imdb_id: 'tt0096697', tvdb_id: 71663 }}
            accept_all: yes
            list_remove:
              - sonarr_list:
                  base_url: {SONARR_BASE_URL}
                  api_key: {SONARR_API_KEY}
                  port: {SONARRR_PORT}

          match_sonarr_list:
            mock:
              - {{ title: 'Game.Of.Thrones.S01E01.1080p.BluRay.x264-FlexGet', imdb_id: 'tt0944947', tvdb_id: 121361 }}
              - {{ title: 'The.Walking.Dead.S01E01.1080p.BluRay.x264-FlexGet', imdb_id: 'tt1520211', tvdb_id: 153021 }}
              - {{ title: 'Breaking.Bad.S01E01.1080p.BluRay.x264-FlexGet', imdb_id: 'tt0903747', tvdb_id: 81189 }}
            list_match:
              from:
                - sonarr_list:
                    base_url: {SONARR_BASE_URL}
                    api_key: {SONARR_API_KEY}
                    port: {SONARRR_PORT}
    """

    def test_sonarr_list_tags(self, execute_task, manager):
        sonarr = SonarrSet(
            {
                'api_key': SONARR_API_KEY,
                'base_url': SONARR_BASE_URL,
                'port': SONARRR_PORT,
                'base_path': '',
            }
        )
        tag_by_id = sonarr._sonarr_request("tag", method="post", data={"label": 'tag_by_id'})['id']
        manager.config['tasks']['clear_and_add_to_sonarr_with_tags']['list_add'][0]['sonarr_list'][
            'tags'
        ].append(tag_by_id)

        execute_task('clear_and_add_to_sonarr_with_tags')
        tags = {t["label"].lower(): t["id"] for t in sonarr._sonarr_request("tag")}
        for show in sonarr._sonarr_request('series'):
            assert sorted(show['tags']) == sorted(
                [tag_by_id, tags.get("tv"), tags.get("othertag")]
            )

    # TODO: each action should be own test case
    def test_sonarr_list_actions(self, execute_task):
        # Begin by clearing and then adding a bunch of series
        task = execute_task('clear_and_add_to_sonarr_list')

        # By using the list as the input we verify that the
        # series added above is returned to us
        task = execute_task('sonarr_list_as_input_plugin')
        assert task.find_entry(series_name='Breaking Bad'), (
            "series should have been present in the list but it wasn't"
        )
        assert task.find_entry(series_name='The Walking Dead'), (
            "series should have been present in the list but it wasn't"
        )
        assert task.find_entry(series_name='Game of Thrones'), (
            "series should have been present in the list but it wasn't"
        )

        # Now we will attempt to remove one existing and one
        # non-existing series which should not affect anything at all
        execute_task('remove_from_sonarr_list')

        # And to verify the list we fetch the list again
        # Sinister 2 should now be missing
        task = execute_task('sonarr_list_as_input_plugin')
        assert task.find_entry(series_name='The Walking Dead'), (
            "series should have been present in the list but it wasn't"
        )
        assert task.find_entry(series_name='Game of Thrones'), (
            "series should have been present in the list but it wasn't"
        )
        assert not task.find_entry(series_name='Breaking Bad'), (
            "series should not be present in the list but it was"
        )

        # Now we will try to match a bunch of input entries with
        # the list. Two of the series should not have been matched.
        task = execute_task('match_sonarr_list')
        assert task.find_entry(
            'accepted', title='Game.Of.Thrones.S01E01.1080p.BluRay.x264-FlexGet'
        ), "series should have been matched but it wasn't"
        assert task.find_entry(
            'accepted', title='The.Walking.Dead.S01E01.1080p.BluRay.x264-FlexGet'
        ), "series should have been matched but it wasn't"
        assert task.find_entry(
            'undecided', title='Breaking.Bad.S01E01.1080p.BluRay.x264-FlexGet'
        ), "series should not have been matched but it was"

        # list_match should have removed all the matched series
        # so no series should remain
        task = execute_task('sonarr_list_as_input_plugin')
        assert len(task.all_entries) == 0, "there should be no series left in the list"
