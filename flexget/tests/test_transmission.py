from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import os
import mock
from flexget.plugins.clients.transmission.client import create_torrent_options
from flexget.entry import Entry

torrent_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'private.torrent')
torrent_url = 'file:///%s' % torrent_file
torrent_info_hash = '09977FE761B8D293AD8A929CCAF2E9322D525A6C'


@mock.patch('transmissionrpc.Client')
class TestTransmission:
    config = """
    tasks:
      download_accepted:
        mock:
          - {title: 'test', url: '""" + torrent_url + """'}
        transmission: {}
        accept_all: yes
      download_undecided:
        mock:
          - {title: 'test', url: '""" + torrent_url + """'}
        transmission: {}
    """

    def test_download_accepted(self, mock, execute_task):
        execute_task('download_accepted')
        mock = mock()
        assert mock.add_torrent.called, 'Didn\'t download accepted entry'
        args = mock.add_torrent.call_args_list[0][0]
        assert len(args) == 2, 'Expected `torrent_file` and `timeout` (2 args), got %s args' % str(len(args))

    def test_download_accepted_learning(self, mock, execute_task):
        execute_task('download_accepted', options={'learn': True})
        mock = mock()
        assert not mock.add_torrent.called, 'Downloaded torrent on learning mode'

    def test_download_undecided(self, mock, execute_task):
        execute_task('download_undecided')
        mock = mock()
        assert not mock.add_torrent.called, 'Downloaded non-accepted entry'


add = 'add'
change = 'change'
post = 'post'
empty_entry = Entry()


# Validates mapping correct config options to transmission
class TestCreateTorrentConfigOptions:
    def test_path(self):
        options = create_torrent_options({'path': 'value'}, empty_entry)
        assert options[add]['download_dir'] == 'value'

    def test_maxupspeed(self):
        options = create_torrent_options({'maxupspeed': 3}, empty_entry)
        assert options[change]['uploadLimit'] == 3
        assert options[change]['uploadLimited'] is True

    def test_maxdownspeed(self):
        options = create_torrent_options({'maxdownspeed': 3}, empty_entry)
        assert options[change]['downloadLimit'] == 3
        assert options[change]['downloadLimited'] is True

    def test_maxconnections(self):
        options = create_torrent_options({'maxconnections': 3}, empty_entry)
        assert options[add]['peer_limit'] == 3

    def test_ratio_global(self):
        # 0 follow the global settings
        options = create_torrent_options({}, empty_entry)
        assert 'seedRatioLimit' not in options[change]
        assert 'seedRatioMode' not in options[change]

    def test_ratio_seed_some(self):
        # 1 override the global settings, seeding until a certain ratio
        options = create_torrent_options({'ratio': 4}, empty_entry)
        assert options[change]['seedRatioLimit'] == 4
        assert options[change]['seedRatioMode'] == 1

    def test_ratio_seed_always(self):
        # 2 override the global settings, seeding regardless of ratio
        options = create_torrent_options({'ratio': -1}, empty_entry)
        assert options[change]['seedRatioLimit'] == -1
        assert options[change]['seedRatioMode'] == 2

    def test_addpaused(self):
        options = create_torrent_options({'addpaused': True}, empty_entry)
        assert options[post]['paused'] is True

    def test_content_filename(self):
        options = create_torrent_options({'content_filename': 'You.Shall.Not.Pass'}, empty_entry)
        assert options[post]['content_filename'] == 'You.Shall.Not.Pass'

    def test_main_file_only(self):
        options = create_torrent_options({'main_file_only': True}, empty_entry)
        assert options[post]['main_file_only'] is True

    def test_main_file_ration(self):
        options = create_torrent_options({'main_file_ratio': 0.6}, empty_entry)
        assert options[post]['main_file_ratio'] == 0.6

    def test_magnetization_timeout(self):
        options = create_torrent_options({'magnetization_timeout': 2}, empty_entry)
        assert options[post]['magnetization_timeout'] == 2

    def test_include_subs(self):
        options = create_torrent_options({'include_subs': True}, empty_entry)
        assert options[post]['include_subs'] is True

    def test_bandwidth_priority(self):
        options = create_torrent_options({'bandwidthpriority': 11}, empty_entry)
        assert options[add]['bandwidthPriority'] == 11

    def test_honour_limits(self):
        options = create_torrent_options({'honourlimits': False}, empty_entry)
        assert options[change]['honorsSessionLimits'] is False

    def test_include_files(self):
        options = create_torrent_options({'include_files': ['Empire', 'Strikes', 'Back']}, empty_entry)
        assert options[post]['include_files'] == ['Empire', 'Strikes', 'Back']

    def test_rename_like_files(self):
        options = create_torrent_options({'rename_like_files': True}, empty_entry)
        assert options[post]['rename_like_files'] is True

    def test_skip_files(self):
        options = create_torrent_options({'skip_files': ['Dragon', 'Reborn']}, empty_entry)
        assert options[post]['skip_files'] == ['Dragon', 'Reborn']

    def test_queue_position(self):
        options = create_torrent_options({'queue_position': 19}, empty_entry)
        assert options[change]['queuePosition'] == 19


# Validates mapping correct entry overriden options to transmission
class TestCreateTorrentEntryOptions:
    def test_path(self):
        options = create_torrent_options({'path': 'value'}, Entry({'path': 'another'}))
        assert options[add]['download_dir'] == 'another'

    def test_maxupspeed(self):
        options = create_torrent_options({'maxupspeed': 3}, Entry({'maxupspeed': 4}))
        assert options[change]['uploadLimit'] == 4
        assert options[change]['uploadLimited'] is True

    def test_maxdownspeed(self):
        options = create_torrent_options({'maxdownspeed': 3}, Entry({'maxdownspeed': 6}))
        assert options[change]['downloadLimit'] == 6
        assert options[change]['downloadLimited'] is True

    def test_maxconnections(self):
        options = create_torrent_options({'maxconnections': 3}, Entry({'maxconnections': 1}))
        assert options[add]['peer_limit'] == 1

    def test_ratio_seed_some(self):
        # 1 override the global settings, seeding until a certain ratio
        options = create_torrent_options({'ratio': 4}, Entry({'ratio': -1}))
        assert options[change]['seedRatioLimit'] == -1
        assert options[change]['seedRatioMode'] == 2

    def test_ratio_seed_always(self):
        # 2 override the global settings, seeding regardless of ratio
        options = create_torrent_options({'ratio': -1}, Entry({'ratio': 4}))
        assert options[change]['seedRatioLimit'] == 4
        assert options[change]['seedRatioMode'] == 1

    def test_addpaused(self):
        options = create_torrent_options({'addpaused': True}, Entry({'addpaused': False}))
        assert options[post]['paused'] is False

    def test_content_filename(self):
        options = create_torrent_options({'content_filename': 'You.Shall.Not.Pass'},
                                         Entry({'content_filename': 'Yes.I.Will'}))
        assert options[post]['content_filename'] == 'Yes.I.Will'

    def test_main_file_only(self):
        options = create_torrent_options({'main_file_only': True}, Entry({'content_filename': 'Yes.I.Will'}))
        assert options[post]['main_file_only'] is True

    def test_main_file_ration(self):
        options = create_torrent_options({'main_file_ratio': 0.6}, Entry({'main_file_ratio': 0.2}))
        assert options[post]['main_file_ratio'] == 0.2

    def test_magnetization_timeout(self):
        options = create_torrent_options({'magnetization_timeout': 2}, Entry({'magnetization_timeout': 4}))
        assert options[post]['magnetization_timeout'] == 4

    def test_include_subs(self):
        options = create_torrent_options({'include_subs': True}, Entry({'include_subs': False}))
        assert options[post]['include_subs'] is False

    def test_bandwidth_priority(self):
        options = create_torrent_options({'bandwidthpriority': 11}, Entry({'bandwidthpriority': 22}))
        assert options[add]['bandwidthPriority'] == 22

    def test_honour_limits(self):
        options = create_torrent_options({'honourlimits': False}, Entry({'honourlimits': True}))
        assert 'honorsSessionLimits' not in options[change]

    def test_include_files(self):
        options = create_torrent_options({'include_files': ['Empire', 'Strikes', 'Back']},
                                         Entry({'include_files': ['Critical', 'Hit!']}))
        assert options[post]['include_files'] == ['Critical', 'Hit!']

    def test_rename_like_files(self):
        options = create_torrent_options({'rename_like_files': True}, Entry({'rename_like_files': False}))
        assert options[post]['rename_like_files'] is False

    def test_skip_files(self):
        options = create_torrent_options({'skip_files': ['Dragon', 'Reborn']},
                                         Entry({'skip_files': ['Ishamael', 'Lanfear']}))
        assert options[post]['skip_files'] == ['Ishamael', 'Lanfear']

    def test_queue_position(self):
        options = create_torrent_options({'queue_position': 19}, Entry({'queue_position': 4}))
        assert options[change]['queuePosition'] == 4
