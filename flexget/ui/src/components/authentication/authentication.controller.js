(function () {
    'use strict';

    angular.module('flexget.components')
        .controller('LoginController', loginController);

    function loginController($stateParams, authService) {
        var vm = this;

        vm.timeout = $stateParams.timeout;
        vm.remember = false;
        vm.error = '';
        vm.credentials = {
            username: '',
            password: ''
        };

        vm.login = function () {
            authService.login(vm.credentials.username, vm.credentials.password, vm.remember)
                .error(function (data) {
                    vm.credentials.password = '';
                    if ('message' in data) {
                        vm.error = data.message;
                    } else {
                        vm.error = 'Error during authentication';
                    }
                });
        };
    }

})();