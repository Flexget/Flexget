(function () {
  'use strict';

  angular.module('flexget.services')
    .provider('route', function($stateProvider, $urlRouterProvider) {
      $urlRouterProvider.otherwise(function ($injector, $location) {
        var $state = $injector.get("$state");
        $state.go("home");
      });

      this.$get = function () {
        return {
          register: function (name, url, controller, template) {
            $stateProvider.state(name, {
              url: url,
              templateUrl: template,
              controller: controller
            });
          }
        }
      }
    })
})();


