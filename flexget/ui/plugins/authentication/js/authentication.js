(function () {
  'use strict';

  var services = angular.module('flexget.services');

  services.factory('auth', function($state, $cookies, $http){
    var loggedIn, prevState, prevParams, timeout;

    loggedIn = false;

    return {
      isLoggedIn: function () {
        if (!loggedIn) {
          var token = $cookies.get("remember_token");
          if (token) {
            loggedIn = true;
          }
        }
        return loggedIn;
      },
      loginConfirmed: function () {
        loggedIn = true;
        timeout = false;
        if (prevState) {
          $state.go(prevState, prevParams);
        } else {
          $state.go('home');
        }
      },
      state: function(state, params) {
        prevState = state;
        prevParams = params;
      }
    }
  });

  services.run(['$rootScope', '$state', 'auth', function ($rootScope, $state, authService) {
    $rootScope.$on('$stateChangeStart', function(event, toState, toParams, fromState, fromParams) {
      if (!authService.isLoggedIn() && toState.name != "login") {
        event.preventDefault();
        $rootScope.$broadcast('event:auth-loginRequired', toState, toParams);
      }
    });
  }]);

  services.config(['$httpProvider', function($httpProvider) {
    $httpProvider.interceptors.push(['$rootScope', '$q', '$injector', function($rootScope, $q, $injector) {
      var loginRequired = function() {
        var stateService = $injector.get('$state');
        var authService = $injector.get('auth');
        authService.state(stateService.current, stateService.params);
        $rootScope.$broadcast('event:auth-loginRequired', true);
      };

      return {
        responseError: function(rejection) {
          if (!rejection.config.ignoreAuthModule) {
            switch (rejection.status) {
              case 401:
                loginRequired();
                break;
              case 403:
                loginRequired();
                break;
            }
          }
          // otherwise, default behaviour
          return $q.reject(rejection);
        }
      };
    }]);
  }]);

})();
