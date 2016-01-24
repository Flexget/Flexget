(function () {
    'use strict';

    angular.module('flexget.plugins.log')
        .controller('logController', logController);

    function logController($scope, $timeout) {
        var vm = this;

        var filterTimeout;
        var logStream = false;

        vm.status = 'Connecting';
        vm.filter = {
            lines: 400,
            search: ''
        };

        vm.stop = function () {
            if (angular.isDefined(filterTimeout)) {
                $timeout.cancel(filterTimeout);
            }
            if (typeof logStream !== 'undefined' && logStream) {
                logStream.abort();
                logStream = false;
                vm.status = "Disconnected";
            }

        };

        vm.refresh = function () {
            // Delay for 1 second before getting search results from server
            if (angular.isDefined(filterTimeout)) {
                $timeout.cancel(filterTimeout);
            }
            filterTimeout = $timeout(function () {
                getLogData()
            }, 1000);
        };

        var getLogData = function () {
            // Disconnect existing log streams
            vm.stop();

            vm.status = "Connecting";
            vm.gridOptions.data = [];

            var queryParams = '?lines=' + vm.filter.lines;
            if (vm.filter.search) {
                queryParams = queryParams + '&search=' + vm.filter.search;
            }

            logStream = oboe({url: '/api/server/log/' + queryParams})
                .start(function () {
                    $scope.$applyAsync(function () {
                        vm.status = "Streaming";
                    });
                })
                .node('{message}', function (node) {
                    $scope.$applyAsync(function () {
                        vm.gridOptions.data.push(node);
                    });
                })
                .fail(function (test) {
                    $scope.$applyAsync(function () {
                        vm.status = "Disconnected";
                    });
                })
        };

        var rowTemplate = '<div class="{{ row.entity.log_level | lowercase }}"' +
            'ng-class="{summary: row.entity.message.startsWith(\'Summary\'), accepted: row.entity.message.startsWith(\'ACCEPTED\')}"><div ' +
            'ng-repeat="(colRenderIndex, col) in colContainer.renderedColumns track by col.uid" ' +
            'class="ui-grid-cell" ' +
            'ng-class="{ \'ui-grid-row-header-cell\': col.isRowHeader }"  ui-grid-cell>' +
            '</div></div>';

        vm.gridOptions = {
            data: [],
            enableSorting: true,
            rowHeight: 20,
            columnDefs: [
                {field: 'timestamp', name: 'Time', cellFilter: 'date', enableSorting: true, width: 120},
                {field: 'log_level', name: 'Level', enableSorting: false, width: 65},
                {field: 'plugin', name: 'Plugin', enableSorting: false, width: 80, cellTooltip: true},
                {field: 'task', name: 'Task', enableSorting: false, width: 65, cellTooltip: true},
                {field: 'message', name: 'Message', enableSorting: false, minWidth: 400, cellTooltip: true}
            ],
            rowTemplate: rowTemplate,
            onRegisterApi: function (gridApi) {
                vm.gridApi = gridApi;
                getLogData();
            }
        };

        // Cancel timer and stop the stream when navigating away
        $scope.$on("$destroy", function () {
            vm.stop();
        });
    }

})
();