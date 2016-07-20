(function () {
    'use strict';

    angular
		.module('plugins.schedule', [
			'angular-cache',

			'blocks.exception',
			'blocks.router'
			//'schemaForm'
		]);
	
	registerPlugin('plugins.schedule');
}());