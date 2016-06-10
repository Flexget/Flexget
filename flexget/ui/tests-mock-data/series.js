var mockSeriesData = (function () {
	return {
		getShows: getShows,
		getShow: getShow,
		getShowMetadata: getShowMetadata
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

	function getShowMetadata() {
		return {
			"airs_dayofweek": "Tuesday",
			"airs_time": "9:00 PM",
			"aliases": [],
			"banner": "http://thetvdb.com/banners/graphical/281470-g5.jpg",
			"content_rating": "TV-14",
			"expired": false,
			"first_aired": "Tue, 17 Mar 2015 00:00:00 GMT",
			"genres": [
				"Action",
				"Comedy",
				"Crime",
				"Drama",
				"Horror"
			],
			"imdb_id": "tt3501584",
			"language": "en",
			"last_updated": "2016-06-09 11:14:09",
			"network": "The CW",
			"overview": "Olivia “Liv” Moore was a rosy-cheeked, disciplined, over-achieving medical resident who had her life path completely mapped out…until the night she attended a party that unexpectedly turned into a zombie feeding frenzy. Now a med sudent-turned-zombie, she takes a job in the coroner's office to gain acces to the brains she must reluctantly eat to maintain her humanity, but with each brain she consumes, she inherits the corpse's memories. With the help of her medical examiner boss and a police detective, she solves homicide cases in order to quiet the disturbing voices in her head. ",
			"posters": [
				"http://thetvdb.com/banners/posters/281470-2.jpg",
				"http://thetvdb.com/banners/posters/281470-1.jpg",
				"http://thetvdb.com/banners/posters/281470-3.jpg",
				"http://thetvdb.com/banners/posters/281470-5.jpg",
				"http://thetvdb.com/banners/posters/281470-4.jpg"
			],
			"rating": 8.4,
			"runtime": 45,
			"series_name": "iZombie",
			"status": "Continuing",
			"tvdb_id": 281470,
			"zap2it_id": "EP01922973"
		}
	}
})();