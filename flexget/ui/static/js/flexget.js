'use strict';


var app = angular.module("flexgetApp", ['ui.router']);

fetchData().then(bootstrapApplication);

function fetchData() {
  var initInjector = angular.injector(["ng"]);
  var $http = initInjector.get("$http");

  return $http.get("/ui/routes").then(function(response) {
    app.constant("appRoutes", response.data);
  }, function(errorResponse) {
    // Handle error case
  });
}

function bootstrapApplication() {
  angular.element(document).ready(function() {
    angular.bootstrap(document, ["flexgetApp"]);
  });
}

app.config(function(appRoutes, $stateProvider, $urlRouterProvider) {
  $urlRouterProvider.otherwise("/home");
  var currentRoute;
  var j = 0;

  for ( ; j < appRoutes.routes.length; j++ ) {
    currentRoute = appRoutes.routes[j];
    $stateProvider.state(currentRoute.name, {
      url: currentRoute.url,
      templateUrl: currentRoute.template_url,
      controller: currentRoute.controller
    });
  }
});


function registerFlexModule(module) {
  angular.module('flexgetApp').requires.push(module.name);
}


app.controller('serverCtrl', ['$scope', '$http', function($scope, $http) {
  $scope.reload = function() {
    $http.get('/api/server/reload/').
    success(function(data, status, headers, config) {
      alert('reloaded');
    }).
    error(function(data, status, headers, config) {
      alert('reloaded failed');
    });
  };

  $scope.shutdown = function() {
    $http.get('/api/server/shutdown/').
    success(function(data, status, headers, config) {
      alert('shutdown');
    }).
    error(function(data, status, headers, config) {
      alert('shutdown failed');
    });
  };
}]);
