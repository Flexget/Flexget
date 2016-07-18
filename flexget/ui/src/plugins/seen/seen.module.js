(function () {
	'use strict';

	angular
		.module('plugins.seen', [
			'angular-cache',

			'blocks.exception',
			'blocks.router'
		]);
	
	registerPlugin('plugins.seen');
})();