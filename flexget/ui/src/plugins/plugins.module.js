(function () {
    'use strict';

    angular
        .module('flexget.plugins', [
			'plugins.execute',
			'plugins.history',
			'plugins.log',
			'plugins.movies',
			'plugins.schedule',
			'plugins.seen',
			'plugins.series'
		]);
})();