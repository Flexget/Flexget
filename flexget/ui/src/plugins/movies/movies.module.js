(function () {
    'use strict';

    angular
		.module("plugins.movies", [
			'blocks.router',
			'blocks.exception',
			'ngMaterial',
			'ngSanitize',
			'angular-cache'
		]);
	
	registerPlugin('plugins.movies');
})();