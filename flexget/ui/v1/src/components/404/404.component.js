/* global angular */
(function () {
    'use strict';

    angular
        .module('components.404')
        .component('notFound', {
            templateUrl: 'components/404/404.tmpl.html',
            controllerAs: 'vm',
            controller: notFoundController
        });

    function notFoundController($state) {
        var vm = this;

        vm.goHome = goHome;

        function goHome() {
            $state.go('flexget.home');
        }
    }
}());
