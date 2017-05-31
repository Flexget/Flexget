/* global angular */
(function () {
    'use strict';

    angular
        .module('flexget', [
            'ngCookies',
            'ngMaterial',
            'ngMessages',
            'ngSanitize',

            'angular-loading-bar',
            'http-etag',
            
            'blocks.error',
            'blocks.exception',
            'blocks.router',
            'blocks.urlInterceptor',

            'flexget.components',
            'flexget.directives',
            'flexget.plugins',

            'ui.router'
        ]);

    function bootstrapApplication() {
        /* Bootstrap app after page has loaded which allows plugins to register */
        angular.element(document).ready(function () {
            angular.bootstrap(document, ['flexget']);
        });
        window.loadingScreen.finish();
    }

    bootstrapApplication();
}());