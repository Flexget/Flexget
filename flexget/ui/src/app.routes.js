(function () {
  'use strict';

  angular.module('flexget')
    .provider('route', routeService)
    .config(routeConfig);

  function routeService($stateProvider) {
    this.$get = function () {
      return {
        register: function (name, url, template) {
          $stateProvider.state('flexget.' + name, {
            url: url,
            template: '<' + template + ' flex layout="row"></' + template + '/>'
          });
        }
      };
    };
  }

  function routeConfig($stateProvider, $urlRouterProvider) {
    $stateProvider
      // 404 & 500 pages
      .state('404', {
        url: '/404',
        templateUrl: '404.tmpl.html',
        controllerAs: 'vm',
        controller: function ($state) {
          var vm = this;
          vm.goHome = function () {
            $state.go('flexget.home');
          };
        }
      })

      .state('flexget', {
        abstract: true,
        templateUrl: 'layout.tmpl.html'
      });

    // set default routes when no path specified
    $urlRouterProvider.when('', '/home');
    $urlRouterProvider.when('/', '/home');

    // always goto 404 if route not found
    $urlRouterProvider.otherwise('/404');

  }
});
