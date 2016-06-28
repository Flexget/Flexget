(function () {
    'use strict';

    angular
        .module('flexget.plugins', [
			'plugins.config',
			'plugins.execute',
			'plugins.history',
			'plugins.log',
			'plugins.movies',
			'plugins.schedule',
			'plugins.seen',
			'plugins.series'
		]);
})();