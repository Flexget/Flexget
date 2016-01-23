(function () {
    'use strict';

    angular.module('flexget.components')
        .controller('LoginController', loginController);

    function loginController($scope, $stateParams, authService) {
        $scope.timeout = $stateParams.timeout;
        $scope.remember = false;
        $scope.error = '';
        $scope.credentials = {
            username: '',
            password: ''
        };

        $scope.login = function () {
            authService.login($scope.credentials.username, $scope.credentials.password, $scope.remember)
                .error(function (data) {
                    $scope.credentials.password = '';
                    if ('message' in data) {
                        $scope.error = data.message;
                    } else {
                        $scope.error = 'Error during authentication';
                    }
                });
        };
    }

})();