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
          var token = $cookies.get("flexgetToken");
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

  var authentication = angular.module('authentication', ['flexget.services']);
  registerModule(authentication);

  authentication.run(function ($rootScope, $state, $http, route, toolBar) {
    route.register('login', '/login?timeout', 'LoginController', 'plugin/authentication/static/login.html');

    $rootScope.$on('event:auth-loginRequired', function (event, timeout) {
      $state.go('login', {'timeout': timeout});
    });

    var logout = function() {
      $http.get('/api/logout/')
        .success(function (data, status, headers, config) {
          $state.go('login');
        });
    };

    toolBar.registerMenuItem('Manage', 'Logout', 'fa fa-sign-out', logout, 255);
  });

  authentication.controller('LoginController', function ($scope, $http, $mdDialog, auth, $stateParams) {
    $scope.timeout = $stateParams.timeout;
    $scope.remember = false;
    $scope.error = '';
    $scope.credentials = {
      username: '',
      password: ''
    };
    $scope.login = function () {
      $http.post('/api/login/?remember=' + $scope.remember, $scope.credentials).success(function() {
        auth.loginConfirmed();
      }).error(function(data) {
        $scope.credentials.password = '';
        if ('message' in data) {
          $scope.error = data.message;
        } else {
          $scope.error = 'Error during authentication';
        }
      });
    };
  });

})();
