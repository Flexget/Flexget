(function () {
    'use strict';

    angular
		.module("plugins.config", [
			'blocks.router',
			'blocks.exception',
			'components.toolbar',
			'ngMaterial',
			'ui.ace',
			'ab-base64',
			'angular-cache'
		]);
	
	registerPlugin('plugins.config');
})();