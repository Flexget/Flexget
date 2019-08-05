/* eslint-disable no-unused-vars */
var mockSchedulesData = (function () {
	return {
		getMockSchedules: getMockSchedules
	};

	function getMockSchedules() {
		return {
			'schedules': [
				{
					'id': 104536512,
					'interval': {
						'hours': 1
					},
					'tasks': [
						'DownloadSeries'
					]
				},
				{
					'id': 104729024,
					'schedule': {
						'hour': 12,
						'minute': 30
					},
					'tasks': 'FillMovieQueue'
				}
			]
		};
	}
}());