/* global angular */
(function () {
    'use strict';

    angular
        .module('components.core')
        .config(themesConfig);

    function themesConfig($mdThemingProvider) {
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