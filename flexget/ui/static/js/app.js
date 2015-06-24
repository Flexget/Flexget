'use strict';

// To dynamically load the routes we need to set a reference
// to the route provider as http is not avaliable during app.config
var $stateProviderReference, $urlRouterProviderReference;
var app = angular.module('flexgetApp', ['ui.router']);

app.factory('menuItems', function ($http) {
    return {
      all: function () {
        return $http({
            url: '/ui/routes',
            method: 'GET'
        });
    }
  };
 });


app.config(function($stateProvider, $urlRouterProvider) {
  $urlRouterProvider.otherwise("/home");

  $stateProviderReference = $stateProvider;
  $urlRouterProviderReference = $urlRouterProvider
});


app.run(['$http', 'menuItems', function($http, menuItems) {
  menuItems.all().success(function (data) {
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
