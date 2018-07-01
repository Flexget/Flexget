/* global angular */
(function () {
    'use strict';

    angular
        .module('components.core')
        .config(coreConfig);

    function coreConfig($httpProvider, $mdThemingProvider, httpEtagProvider) {
        httpEtagProvider.setDefaultCacheConfig({
            cacheResponseHeaders: true
        })
            .defineCache('httpEtagCache');
        $httpProvider.useLegacyPromiseExtensions(false);

        $mdThemingProvider.theme('default')
            .primaryPalette('orange', {
                default: '800'
            })
            .accentPalette('deep-orange', {
                default: '500'
            })
            .warnPalette('amber');
    }

}());