/* global angular */
(function () {
    'use strict';

    angular
        .module('components.core')
        .provider('flexTheme', flexTheme);

    function flexTheme($mdThemingProvider) {
        return {
            $get: function () {
                return {
                    getPaletteColor: function (paletteName, hue) {
                        if (
                            angular.isDefined($mdThemingProvider._PALETTES[paletteName])
                            && angular.isDefined($mdThemingProvider._PALETTES[paletteName][hue])
                        ) {
                            return $mdThemingProvider._PALETTES[paletteName][hue];
                        }
                    },
                    rgba: $mdThemingProvider._rgba,
                    palettes: $mdThemingProvider._PALETTES,
                    themes: $mdThemingProvider._THEMES,
                    parseRules: $mdThemingProvider._parseRules
                };
            }
        };
    }
}());