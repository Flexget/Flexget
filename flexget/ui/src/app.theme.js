(function () {
  'use strict';

  angular
  .module('flexget')
  .config(themesConfig)
  .provider('flexTheme', flexTheme);

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
          parseRules: $mdThemingProvider._parseRules,
        };
      },
    };
  }
})();
