(function () {
	'use strict';

	angular
		.module('blocks.urlInterceptor')
		.factory('urlInterceptor', urlInterceptor)
		.config(configInterceptor);

	function configInterceptor($httpProvider) {
		$httpProvider.interceptors.push('urlInterceptor')
	};

	function urlInterceptor($q, $log) {
		var service = {
			request: request
		};
		return service;

		function request(config) {
			if (config.url.startsWith('/api/') && !config.url.endsWith('/')) {
				config.url += '/';
			}
			return config;
		}
	}
})();