(function() {
  'use strict';

  angular
	  .module('flexget.components.requestInterceptor')
	  .factory('urlInterceptor', urlInterceptor)
	  .config(function ($httpProvider) {
		  $httpProvider.interceptors.push('urlInterceptor')
	  });

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
