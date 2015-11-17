(function () {
  'use strict';

  var services = angular.module('flexget.services');

  /* Authentication Service */
  services.factory('authService', function($state, $cookies, $http, $q){
    var loggedIn, prevState, prevParams;

    loggedIn = false;

    return {
      loggedIn: function() {
        var def = $q.defer();

        if (loggedIn) {
          def.resolve(loggedIn);
        } else {
          $http.get("/api/server/version/")
              .success(function() {
                def.resolve();
              })
              .error(function(data) {
                def.reject()
              })
        }

        return def.promise;
      },
      login: function (username, password, remember) {
        if (!remember) {
          remember = false;
        }

        return $http.post('/api/login/?remember=' + remember, {username: username, password: password})
            .success(function() {
              loggedIn = true;

              if (prevState) {
                $state.go(prevState, prevParams);
              } else {
                $state.go('home');
              }

            })
      },
      state: function(state, params) {
        prevState = state;
        prevParams = params;
      }
    }
  });

  /* Ensure user is authenticated when changing states (pages) unless we are on the login page */
  services.run(['$rootScope', '$state', 'authService', function ($rootScope, $state, authService) {
    $rootScope.$on('$stateChangeStart', function(event, toState, toParams) {
      if (toState.name == "login") {
        return
      }

      authService.loggedIn()
          .then(function(loggedIn){
            // already logged in
          }, function() {
            // Not logged in
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
        var authService = $injector.get('authService');
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