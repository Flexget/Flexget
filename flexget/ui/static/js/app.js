define(['angularAMD', 'ui-router'], function (angularAMD) {
  // To dynamically load the routes we need to set a reference
  // to the route provider as http is not avaliable during app.config
  var $stateProviderReference;
  var app = angular.module("webapp", ['ui.router']);

  app.config(function($stateProvider) {
    $stateProviderReference = $stateProvider;
  });

  app.run(['$http',
    function($http) {
      $http.get('/ui/routes').success(function (data) {
        var currentRoute;
        var j = 0;

        for ( ; j < data.routes.length; j++ ) {
          currentRoute = data.routes[j];
          $stateProviderReference.state(currentRoute.name, angularAMD.route({
            url: currentRoute.url,
            templateUrl: currentRoute.template_url,
            controller: currentRoute.controller,
            controllerUrl: currentRoute.controller_url
          }));
        }
      });

    }]);

  return angularAMD.bootstrap(app);
});