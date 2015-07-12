'use strict';

var logViewModule = angular.module("logViewModule", ['ngOboe', 'ui.grid', 'ui.grid.autoResize']);

registerFlexModule(logViewModule);

logViewModule.controller('LogViewCtrl',
  ['$scope', '$timeout', '$filter', 'Oboe', 'uiGridConstants',
    function($scope, $timeout, $filter, Oboe, uiGridConstants) {
      $scope.title = 'Server Log';

      $scope.log = [];
      $scope.logStream = null;
      $scope.lines = 400;

      var logLevels = {
        CRITICAL: 50,
        ERROR: 40,
        WARNING: 30,
        VERBOSE: 15,
        DEBUG: 10,
        INFO: 20
      };

      var getData = function() {
        if ($scope.logStream) {
          $scope.logStream.abort();
        }
        console.log("getting log data")
        $scope.log = [];
        $scope.gridOptions.data = $scope.log

        Oboe({
          url: '/api/server/log/?lines=' + $scope.lines,
          pattern: '{message}',
          start: function(stream) {
            $scope.logStream = stream;
          }
        }).then(function() {
          // finished loading
        }, function(error) {
          // handle errors
        }, function(node) {
          $scope.log.push(node);
        });
      };

      var rowTemplate = function() {
        return '<div class="{{ row.entity.levelname | lowercase }}"' +
          'ng-class="{summary: row.entity.message.startsWith(\'Summary\'), accepted: row.entity.message.startsWith(\'ACCEPTED\')}"><div ' +
          'ng-repeat="(colRenderIndex, col) in colContainer.renderedColumns track by col.uid" ' +
          'class="ui-grid-cell" ' +
          'ng-class="{ \'ui-grid-row-header-cell\': col.isRowHeader }"  ui-grid-cell>' +
          '</div></div>'
      };

      $scope.gridOptions = {
        data: $scope.log,
        enableSorting: true,
        rowHeight: 20,
        enableFiltering: true,
        columnDefs: [
          {field: 'asctime', name: 'Time', cellFilter: 'date', enableSorting: true, width: 105},
          {field: 'levelname', name: 'Level', enableSorting: false, width: 65,
            filter: {
              type: uiGridConstants.filter.SELECT,
              selectOptions: [
                {value: logLevels.ERROR, label: 'ERROR'},
                {value: logLevels.WARNING, label: 'WARNING'},
                {value: logLevels.INFO, label: 'INFO'},
                {value: logLevels.VERBOSE, label: 'VERBOSE'},
                {value: logLevels.DEBUG, label: 'DEBUG'}
              ],
              condition: function(level, cellValue) {
                return logLevels[cellValue] >= level;
              }
            }
          },
          {field: 'name', name: 'Name', enableSorting: false, width: 80, cellTooltip: true},
          {field: 'task', name: 'Task', enableSorting: false, width: 65, cellTooltip: true},
          {field: 'message', name: 'Message', enableSorting: false, minWidth: 400, cellTooltip: true}
        ],
        rowTemplate: rowTemplate(),
        onRegisterApi: function(gridApi) {
          getData();
          $scope.gridApi = gridApi;
          $scope.gridApi.core.on.filterChanged($scope, function() {
            // Delay for 1 second before getting filtered results from server
            if (angular.isDefined($scope.filterTimeout)) {
              $timeout.cancel($scope.filterTimeout);
            }
            $scope.filterTimeout = $timeout(function () {
              getData()
            }, 1000);
          });
        }
      };

      // Cancel timer and stop the stream
      $scope.$on("$destroy", function() {
        if (angular.isDefined($scope.filterTimeout)) {
          $timeout.cancel($scope.filterTimeout);
        }
        if (logStream) {
          logStream.abort();
        }
      });
    }]);