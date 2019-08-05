/* global angular */
(function () {
    'use strict';

    angular
        .module('plugins.log')
        .component('logView', {
            templateUrl: 'plugins/log/log.tmpl.html',
            controllerAs: 'vm',
            controller: logController
        });

    function logController($scope, logService) {
        var vm = this;

        vm.$onInit = activate;
        vm.start = start;
        vm.clear = clear;
        vm.toggle = toggle;
        vm.refresh = refresh;
        vm.$onDestroy = destroy;
        vm.stop = stop;

        vm.filter = {
            lines: 400,
            search: ''
        };

        vm.refreshOpts = {
            debounce: 1000
        };

        var gridApi;

        function activate() {
            vm.start();
        }

        function toggle() {
            if (vm.status === 'Disconnected') {
                vm.start();
            } else {
                vm.stop();
            }
        }

        function clear() {
            vm.gridOptions.data = [];
        }

        function stop() {
            if (typeof vm.stream !== 'undefined' && vm.stream) {
                vm.stream.abort();
                vm.stream = false;
                vm.status = 'Disconnected';
            }
        }

        function refresh() {
            // Disconnect existing log streams
            vm.stop();

            vm.start();
        }

        function start() {
            vm.status = 'Connecting';
            vm.gridOptions.data = [];

            var queryParams = '?lines=' + vm.filter.lines;
            if (vm.filter.search) {
                queryParams = queryParams + '&search=' + vm.filter.search;
            }

            vm.stream = logService.startLogStream(queryParams);

            vm.stream.start(startFunction)
                .message(messageFunction)
                .catch(failFunction);

            function startFunction() {
                vm.status = 'Streaming';
            }

            function messageFunction(message) {
                vm.gridOptions.data.push(message);
                gridApi.core.notifyDataChange('row');
            }

            function failFunction() {
                vm.status = 'Disconnected';
            }
        }
        
        vm.gridOptions = {
            data: [],
            enableSorting: true,
            rowHeight: 20,
            columnDefs: [
                { field: 'timestamp', name: 'Time', cellFilter: 'date', enableSorting: true, width: 120 },
                { field: 'log_level', name: 'Level', enableSorting: false, width: 65 },
                { field: 'plugin', name: 'Plugin', enableSorting: false, width: 80, cellTooltip: true },
                { field: 'task', name: 'Task', enableSorting: false, width: 65, cellTooltip: true },
                { field: 'message', name: 'Message', enableSorting: false, minWidth: 400, cellTooltip: true }
            ],
            rowTemplate: 'row-template.html',
            onRegisterApi: function (api) {
                gridApi = api;
            }
        };

        // Cancel timer and stop the stream when navigating away
        function destroy() {
            vm.stop();
        }
    }

}());