(function () {
	'use strict';

	angular
		.module('plugins.log', [
			'blocks.router',
			'components.toolbar'
			//'ui.grid',
			//'ui.grid.autoResize',
			//'ui.grid.autoScroll'
		]);

	registerPlugin('plugins.log');
})();