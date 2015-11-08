(function () {
  'use strict';

  var authentication = angular.module('authentication', ['flexget.services']);
  registerModule(authentication);

  /* Register login page and redirect to page when login is required */
  authentication.run(function ($rootScope, $state, $http, route, toolBar) {
    route.register('login', '/login?timeout', 'LoginController', 'plugin/authentication/static/login.html');

    $rootScope.$on('event:auth-loginRequired', function (event, timeout) {
      $state.go('login', {'timeout': timeout});
    });

    var logout = function() {
      $http.get('/api/logout/')
          .success(function () {
            $state.go('login');
          });
    };

    toolBar.registerMenuItem('Manage', 'Logout', 'fa fa-sign-out', logout, 255);
  });

  authentication.controller('LoginController', function ($scope, $http, $mdDialog, $state, $stateParams, authService) {
    $scope.timeout = $stateParams.timeout;
    $scope.remember = false;
    $scope.error = '';
    $scope.credentials = {
      username: '',
      password: ''
    };

    $scope.login = function () {
      authService.login($scope.credentials.username, $scope.credentials.password, $scope.remember)
          .error(function(data) {
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
