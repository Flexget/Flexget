/* global angular */
(function () {
    'use strict';

    angular
        .module('blocks.urlInterceptor')
        .config(configInterceptor);

    function configInterceptor($httpProvider) {
        $httpProvider.interceptors.push('urlInterceptor');
    }
}());