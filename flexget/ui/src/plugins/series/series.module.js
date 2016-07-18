(function () {
    'use strict';

    angular
		.module('plugins.series', [
			'ngMaterial',
			
			'angular-cache',

			'blocks.exception',
			'blocks.router'
		]);
	
	registerPlugin('plugins.series');
})();