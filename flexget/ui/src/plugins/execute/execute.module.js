(function () {
	'use strict';

	angular
		.module("plugins.execute", [
			'blocks.router',
			'blocks.exception'
			//'ui.grid',
			//'ui.grid.autoResize',
			//'angular-spinkit'
		]);
	
	registerPlugin('plugins.execute');
})();