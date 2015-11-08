(function () {
  'use strict';

  var services = angular.module('flexget.services');

  /* Authentication Service */
  services.factory('auth', function($state, $cookies, $http, $q){
    var loggedIn, prevState, prevParams;

    loggedIn = false;

    return {
      isLoggedIn: function () {
        /*
         Call login api to check if authentication is still valid unless
         loggedIn is true which means it's already been checked
         */

        var deferred = $q.defer();

        if (loggedIn) {
          deferred.deferred.resolve(true)
        } else {
          $http.get('/api/login/')
            .success(function () {
              deferred.resolve(true);
            }).error(function (msg) {
              deferred.reject(msg);
            });
        }
        return deferred.promise;
      },
      loginConfirmed: function () {
        /* Call to go back to previous page after authentication */
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

  /* Ensure user is authenticated when changing states (pages) unless we are on the login page */
  services.run(['$rootScope', '$state', 'auth', function ($rootScope, $state, authService) {
    $rootScope.$on('$stateChangeStart', function(event, toState, toParams) {
      if (toState.name == "login") {
        return
      }
      authService.isLoggedIn()
        .error(function() {
          event.preventDefault();
          authService.state(toState, toParams);
          $rootScope.$broadcast('event:auth-loginRequired', false);
        });
    });
  }]);

  /* Intercept 401/403 http return codes and redirect to login page */
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