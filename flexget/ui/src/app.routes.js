(function () {
    'use strict';

    angular.module('flexget')
        .provider('route', routeService);

    function routeService($stateProvider, $urlRouterProvider) {
        $urlRouterProvider.otherwise(function ($injector) {
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
    }

})();