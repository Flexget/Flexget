(function () {
  'use strict';

  var app = angular.module('flexget', ['ui.router', 'ngMaterial', 'ngCookies', 'flexget.services']);

  function bootstrapApplication() {
    angular.element(document).ready(function () {
      angular.bootstrap(document, ['flexget']);
    });
    window.loading_screen.finish();
  }

  app.config(function ($mdThemingProvider, $mdIconProvider) {
    $mdIconProvider.fontSet('fa', 'fa');
    $mdThemingProvider.theme('default').primaryPalette('orange');
  });

  // flexget.services can be used by plugins to access flexget services in module.config and module.run
  angular.module('flexget.services', []);

  bootstrapApplication();
})();