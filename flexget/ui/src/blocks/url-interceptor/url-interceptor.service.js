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
            if (config.url.startsWith('/api/') && !config.url.endsWith('/')) {
                config.url += '/';
            }
            return config;
        }
    }
}());