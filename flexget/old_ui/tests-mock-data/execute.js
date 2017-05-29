/* eslint-disable no-unused-vars */
var mockExecuteData = (function () {
	return {
		getMockQueue: getMockQueue,
		getMockTasks: getMockTasks
	};

	function getMockQueue() {
		return {
			'tasks': [
				{
					'current_phase': 'input',
					'current_plugin': 'discover',
					'id': 140228,
					'name': 'DownloadMovies'
				}
			]
		};
	}

	function getMockTasks() {
		return {
			'tasks': [
				{
					'config': {
						'disable': [
							'seen',
							'seen_info_hash'
						],
						'list_add': [
							{
								'movie_list': 'Testing'
							}
						],
						'no_entries_ok': true,
						'seen': 'local',
						'template': 'no_global',
						'trakt_list': {
							'account': 'Testing',
							'list': 'Testing',
							'strip_dates': false,
							'type': 'movies'
						}
					},
					'name': 'FillMovieQueue'
				},
				{
					'config': {
						'disable': [
							'seen',
							'seen_info_hash',
							'backlog'
						],
						'discover': {
							'from': [
								{
									'torrentleech': {
										'password': 'Pass',
										'rss_key': 'rss-key',
										'username': 'User'
									}
								}
							],
							'interval': '3 hour',
							'release_estimations': 'auto',
							'what': [
								{
									'movie_list': 'Testing'
								}
							]
						},
						'quality': '<=720p hdrip+',
						'require_field': [
							'tmdb_name',
							'tmdb_year'
						],
						'tmdb_lookup': true
					},
					'name': 'DownloadMovies'
				}
			]
		};
	}
}());