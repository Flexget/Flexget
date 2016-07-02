(function () {
    'use strict';

    angular
		.module('plugins.series', [
			'blocks.router',
			'blocks.exception',
			'angular-cache',
			'ngMaterial'
		]);
	
	registerPlugin('plugins.series');
})();