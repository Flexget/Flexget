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

    function statusController($scope, $filter, statusService) {
        var vm = this;
        
        vm.$onInit = activate;
        vm.timeSorter = timeSorter;

        vm.tableData = {
            data: [],
            'table-row-id-key': 'id',
            'column-keys': [
                'name',
                'last_execution.start',
                'last_execution.produced',
                'last_execution.accepted',
                'last_execution.rejected',
                'last_execution.failed'
            ]
        }

        // Needs to use $scope, mdDataTable takes private scopes, so using vm doesn't work        
        $scope.getSuccess = getSuccessValue;
        
        function getSuccessValue(rowId) {
            var value = $filter('filter')(vm.tableData.data, { id: rowId })[0];
            return value.last_execution.succeeded;
        }

        function timeSorter(a, b) {
            return new Date(b) - new Date(a);
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
            vm.tableData.data = response.data;
        }
    }
}());