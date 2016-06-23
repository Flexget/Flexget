(function () {
    'use strict';

    angular
		.module("plugins.history", [
			'blocks.router',
			'blocks.exception',
			'angular.filter',
			'angular-cache'
		]);
})();