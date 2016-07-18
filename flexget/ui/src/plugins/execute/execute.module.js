(function () {
	'use strict';

	angular
		.module("plugins.execute", [
			'blocks.exception',
			'blocks.router'
		]);
	
	registerPlugin('plugins.execute');
})();