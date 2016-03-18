(function () {
  'use strict';

  angular
  .module('flexget', [
    'ui.router',
    'ngMaterial',
    'ngCookies',
    'ngMessages',
    'angular-loading-bar',
    'flexget.components',
    'flexget.directives',
    'flexget.services'
  ]);

  function bootstrapApplication() {
    /* Bootstrap app after page has loaded which allows plugins to register */
    angular.element(document).ready(function () {
      angular.bootstrap(document, ['flexget']);
    });
    window.loadingScreen.finish();
  }

  bootstrapApplication();
})();
