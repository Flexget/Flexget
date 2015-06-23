'use strict';

window.$ = window.jQuery = require('jquery')
require('bootstrap');
require('./adminlte-2.1.2');

var angular = require('angular');
require('angular-ui-router');
require('angular-schema-form');

//TODO: HACK..
require('./node_modules/angular-schema-form/dist/bootstrap-decorator');


// To dynamically load the routes we need to set a reference
// to the route provider as http is not avaliable during app.config
var $stateProviderReference, $urlRouterProviderReference;
var app = angular.module('flexgetApp', ['ui.router']);

app.config(function($stateProvider, $urlRouterProvider) {
  $stateProviderReference = $stateProvider;
  $urlRouterProviderReference = $urlRouterProvider
});

app.run(['$http', function($http) {
  $http.get('/ui/routes').success(function (data) {
    $urlRouterProviderReference.otherwise("/home");
    var currentRoute;
    var j = 0;

    for ( ; j < data.routes.length; j++ ) {
      currentRoute = data.routes[j];
      $stateProviderReference.state(currentRoute.name, {
        url: currentRoute.url,
        templateUrl: currentRoute.template_url,
        controller: currentRoute.controller
      });
    }
  });
}]);

require('../../plugins');
