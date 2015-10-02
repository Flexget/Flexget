'use strict';

var app = angular.module('flexgetApp', ['ui.router', 'ngMaterial']);

function bootstrapApplication() {
  angular.element(document).ready(function() {
    angular.bootstrap(document, ['flexgetApp']);
  });
}

app.config(function($stateProvider, $urlRouterProvider, $mdThemingProvider, $mdIconProvider) {
  $mdIconProvider.fontSet('fa', 'fa');
  $mdThemingProvider.theme('default')
    .primaryPalette('orange');

  $urlRouterProvider.otherwise('/home');
  var currentRoute;
  var j = 0;

  for ( ; j < app.routes.length; j++ ) {
    currentRoute = app.routes[j];
    $stateProvider.state(currentRoute.name, {
      url: currentRoute.url,
      templateUrl: currentRoute.template,
      controller: currentRoute.controller
    });
  }
});

bootstrapApplication();