(function () {
    'use strict';

    angular
		.module("plugins.config", [
			'blocks.router',
			'blocks.exception',
			'ngMaterial',
			'ui.ace',
			'ab-base64',
			'angular-cache'
		]);
})();