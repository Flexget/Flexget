/* global angular */
(function () {
    'use strict';

    angular
        .module('blocks.urlInterceptor')
        .factory('urlInterceptor', urlInterceptor);

    function urlInterceptor() {
        return {
            request: request
        };

        function request(config) {
            // Make sure api requests end with /
            if (config.url.contains('api') && !config.url.endsWith('/')) {
                config.url += '/';
            }

            // Make sure requests don't start with / (so it's able to use base_url)            
            if (config.url.contains('api') && config.url.startsWith('/')) {
                config.url = config.url.substring(1);
            }

            return config;
        }
    }
}());
