(function () {
    'use strict';

    angular
		.module('plugins.schedule', [
			'blocks.router',
			'blocks.exception',
			'angular-cache'
			//'schemaForm'
		]);
	
	registerPlugin('plugins.schedule');
})();