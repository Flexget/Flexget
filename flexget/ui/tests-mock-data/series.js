var mockSeriesData = (function () {
	return {
		getShows: getShows,
		getShow: getShow
	};

	function getShows() {
		return {
			"page": 1,
			"page_size": 10,
			"shows": [
				{
					"alternate_names": [],
					"begin_episode": {
						"episode_id": 691,
						"episode_identifier": "S02E03"
					},
					"in_tasks": [],
					"latest_downloaded_episode": {
						"episode_age": "18d 13h",
						"episode_id": 749,
						"episode_identifier": "S02E07",
						"last_downloaded_release": {
							"release_downloaded": true,
							"release_episode_id": 749,
							"release_first_seen": "Mon, 23 May 2016 15:29:06 GMT",
							"release_id": 6649,
							"release_proper_count": 0,
							"release_quality": "1080p webdl h264 dd5.1",
							"release_title": "Fear The Walking Dead S02E07 1080p WEB-DL DD5 1 H264-RARBG"
						},
						"number_of_episodes_behind": 0
					},
					"show_id": 20,
					"show_name": "Fear the Walking Dead"
				},
				{
					"alternate_names": [],
					"begin_episode": {
						"episode_id": 753,
						"episode_identifier": "S27E01"
					},
					"in_tasks": [],
					"latest_downloaded_episode": {
						"episode_age": "32d 15h",
						"episode_id": 731,
						"episode_identifier": "S27E20",
						"last_downloaded_release": {
							"release_downloaded": true,
							"release_episode_id": 731,
							"release_first_seen": "Mon, 09 May 2016 05:29:24 GMT",
							"release_id": 6411,
							"release_proper_count": 0,
							"release_quality": "1080p hdtv h264",
							"release_title": "The Simpsons s27e20 To Courier With Love 1080p HDTV x264 mkv-[Zeus]"
						},
						"number_of_episodes_behind": 2
					},
					"show_id": 38,
					"show_name": "The Simpsons"
				},
				{
					"alternate_names": [],
					"begin_episode": {
						"episode_id": 699,
						"episode_identifier": "S03E01"
					},
					"in_tasks": [],
					"latest_downloaded_episode": {
						"episode_age": "58d 15h",
						"episode_id": 670,
						"episode_identifier": "S02E19",
						"last_downloaded_release": {
							"release_downloaded": true,
							"release_episode_id": 670,
							"release_first_seen": "Wed, 13 Apr 2016 05:29:50 GMT",
							"release_id": 5789,
							"release_proper_count": 0,
							"release_quality": "1080p hdtv h264",
							"release_title": "iZombie S02E19 1080p HDTV X264 DIMENSION rartv"
						},
						"number_of_episodes_behind": 1
					},
					"show_id": 4,
					"show_name": "iZombie"
				},
			],
			"total_number_of_pages": 3,
			"total_number_of_shows": 23
		}
	};

	function getShow() {
		return {
			"alternate_names": [],
			"begin_episode": {
				"episode_id": 673,
				"episode_identifier": "S05E17"
			},
			"in_tasks": [],
			"latest_downloaded_episode": {
				"episode_age": "16d 5h",
				"episode_id": 752,
				"episode_identifier": "S05E24",
				"last_downloaded_release": {
					"release_downloaded": true,
					"release_episode_id": 752,
					"release_first_seen": "Wed, 25 May 2016 15:29:52 GMT",
					"release_id": 6681,
					"release_proper_count": 0,
					"release_quality": "1080p webdl h264 aac",
					"release_title": "Awkward S05E24 Happy Campers Happier Trails 1080p WEB DL AAC2 0 H264 Oosh rartv"
				},
				"number_of_episodes_behind": 0
			},
			"show_id": 1,
			"show_name": "Awkward."
		}
	}
})();