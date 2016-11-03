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
        
        vm.data = {
            data: [],
            'column-keys': [
                'name',
                'last_execution.start',
                'last_execution.produced',
                'last_execution.accepted',
                'last_execution.rejected',
                'last_execution.failed',
            ]
        }

        vm.$onInit = activate;

        function activate() {
            getStatus();
        }

        function getStatus() {
            statusService.getStatus()
                .then(setStatuses)
                .cached(setStatuses);
        }
        
        function setStatuses(response) {
            vm.data.data = response.data;
        }
    }
}());