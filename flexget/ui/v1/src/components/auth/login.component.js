/* global angular */
(function () {
    'use strict';

    angular
        .module('components.auth')
        .component('login', {
            templateUrl: 'components/auth/login.tmpl.html',
            controllerAs: 'vm',
            controller: loginController
        });

    function loginController($stateParams, authService) {
        var vm = this;

        vm.timeout = $stateParams.timeout;
        vm.login = login;
        vm.credentials = {};

        function login() {
            authService.login(vm.credentials, vm.remember)
                .catch(function (data) {
                    vm.credentials.password = '';
                    if (data.message) {
                        vm.error = data.message;
                    } else {
                        vm.error = 'Error during authentication';
                    }
                });
        }
    }
}());