/* global angular */
(function () {
    'use strict';

    angular
        .module('components.core')
        .config(coreConfig);

    function coreConfig($httpProvider, $mdThemingProvider) {
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