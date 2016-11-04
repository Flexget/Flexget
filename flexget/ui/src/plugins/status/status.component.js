/* global angular */
(function () {
    'use strict';

    angular
        .module('plugins.status')
        .component('statusView', {
            templateUrl: 'plugins/status/status.tmpl.html',
            controllerAs: 'vm',
            controller: statusController
        });

    function statusController(statusService) {
        var vm = this;
        
        vm.$onInit = activate;
        vm.numberSorter = numberSorter;
        vm.timeSorter = timeSorter;

        function timeSorter(a, b) {
            return new Date(b) - new Date(a);
        }

        function numberSorter(a, b) {
            var numberA = parseInt(a);
            var numberB = parseInt(b);
        
            if (isNaN(numberA)) {
                return 1;
            } else if (isNaN(numberB)) {
                return -1;
            } else if (numberA === numberB) {
                return 0;
            }
            return (numberA > numberB ? -1 : 1);
        }

        function activate() {
            getStatus();
        }

        function getStatus() {
            statusService.getStatus()
                .then(setStatuses)
                .cached(setStatuses);
        }
        
        function setStatuses(response) {
            vm.tasks = response.data;
        }
    }
}());