var mockExecuteData = (function () {
	return {
		getMockQueue: getMockQueue
	};

	function getMockQueue() {
		return {
			"tasks": [
				{
					"current_phase": "input",
					"current_plugin": "discover",
					"id": 140228,
					"name": "DownloadMovies"
				}
			]
		}
	}
})();