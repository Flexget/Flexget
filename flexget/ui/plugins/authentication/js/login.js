(function () {
  'use strict';

  var login = angular.module('login', ['flexget.services']);
  registerModule(login);

  login.config(function(routeProvider) {
    routeProvider.register('login', '/login?timeout', 'LoginController', 'plugin/authentication/static/login.html');
  });

  login.controller('LoginController', function ($scope, $http, $mdDialog, auth, $stateParams) {
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

  login.run(['$rootScope', '$state', function ($rootScope, $state) {
    $rootScope.$on('event:auth-loginRequired', function (event, timeout) {
        $state.go('login', {'timeout': timeout});
    });
  }]);

})();