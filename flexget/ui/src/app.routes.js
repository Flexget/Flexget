(function () {
    'use strict';

    angular.module('flexget')
        .provider('route', routeService)
        .config(routeConfig);

    function routeService($stateProvider, $urlRouterProvider) {
        $urlRouterProvider.otherwise(function ($injector) {
            var $state = $injector.get("$state");
            $state.go("flexget.home");
        });

        this.$get = function () {
            return {
                register: function (name, url, controller, template) {
                    $stateProvider.state('flexget.' + name, {
                        url: url,
                        templateUrl: template,
                        controller: controller,
                        controllerAs: 'vm'
                    });
                }
            }
        }
    }

    function routeConfig($stateProvider) {
        $stateProvider
            .state('flexget', {
                abstract: true,
                templateUrl: 'layout.tmpl.html',
            });
    }

})();