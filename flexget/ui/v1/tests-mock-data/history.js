/* eslint-disable no-unused-vars */
var mockHistoryData = (function () {
	return {
		getMockHistory: getMockHistory
	};

	function getMockHistory() {
		return {
			'entries': [
				{
					'details': 'Accepted by series (reason: target quality)',
					'filename': null,
					'id': 2267,
					'task': 'DownloadSeries',
					'time': '2016-05-24T07:29:59.039488',
					'title': 'Containment S01E06 1080p HDTV X264-DIMENSION[rartv]',
					'url': 'https://torcache.net/torrent/345D66A75FCEE92BE701970EE0030E641BF5915D.torrent?title=[kat.cr]containment.s01e06.1080p.hdtv.x264.dimension.rartv'
				},
				{
					'details': 'Accepted by accept_all',
					'filename': null,
					'id': 2266,
					'task': 'FillMovieQueue',
					'time': '2016-05-24T03:52:01.924238',
					'title': 'Autumn (2009)',
					'url': 'https://trakt.tv/movies/autumn-2009'
				},
				{
					'details': 'Accepted by list_accept',
					'filename': null,
					'id': 2265,
					'task': 'RemoveCollectedMovies',
					'time': '2016-05-24T03:00:09.372575',
					'title': 'The Cell 2 (2009)',
					'url': 'https://trakt.tv/movies/the-cell-2-2009'
				}
			],
			'pages': 114
		};
	}
}());
