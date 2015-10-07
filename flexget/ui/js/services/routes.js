(function () {
  'use strict';

  angular.module('flexget.services')
    .provider('route', function($stateProvider, $urlRouterProvider) {
      $urlRouterProvider.otherwise('/home');

      this.register = function(name, url, controller, template) {
        $stateProvider.state(name, {
          url: url,
          templateUrl: template,
          controller: controller
        });
      };

      this.$get = function() {};

    });

})();


