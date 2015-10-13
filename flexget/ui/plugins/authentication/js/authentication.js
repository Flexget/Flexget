(function () {
  'use strict';

  var services = angular.module('flexget.services');

  services.factory('auth', function($state, $cookies, $http){
    var loggedIn, prevState, prevParams;

    loggedIn = false;

    return {
      isLoggedIn: function () {
        if (!loggedIn) {
          //TODO: Check if token still valid
          var token = $cookies.get("flexget_token");
          if (token) {
            loggedIn = true;
          }
        }
        return loggedIn;
      },
      loginConfirmed: function () {
        loggedIn = true;
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
        authService.state(toState, toParams);
        $rootScope.$broadcast('event:auth-loginRequired', false);
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
