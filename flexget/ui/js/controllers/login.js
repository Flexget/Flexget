'use strict';

app.requires.push('http-auth-interceptor');

app.controller('LoginController', function ($scope, $http, $mdDialog, authService) {
  $scope.error = '';

  var doLogin = function() {
    var LoginModalController = function($scope) {
      $scope.error = '';
      $scope.credentials = {
        username: '',
        password: ''
      };
      $scope.login = function () {
        $http.post('/api/login/', $scope.credentials).success(function() {
          authService.loginConfirmed();
        }).error(function(data) {
          $scope.credentials.password = '';
          if ('message' in data) {
            $scope.error = data.message;
          } else {
            $scope.error = 'Error during authentication';
          }
        });
      }
    };
    $mdDialog.show({
      templateUrl: 'static/partials/login.html',
      parent: angular.element(document.body),
      controller: LoginModalController
    });

  };

  var closeLogin = function() {
    $mdDialog.hide();
  };

  $scope.$on('event:auth-loginRequired', doLogin);
  $scope.$on('event:auth-loginConfirmed', closeLogin)
});
