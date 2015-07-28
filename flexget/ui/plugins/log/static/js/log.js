'use strict';

var logViewModule = angular.module("logViewModule", ['ngOboe', 'ui.grid', 'ui.grid.autoResize']);

registerFlexModule(logViewModule);

logViewModule.controller('LogViewCtrl',
    ['$scope', '$timeout', '$filter', 'Oboe', 'uiGridConstants',
      function($scope, $timeout, $filter, Oboe, uiGridConstants) {
        $scope.title = 'Server Log';

        $scope.log = [];
        $scope.logStream = false;
        $scope.lines = 400;
        $scope.autoScroll = true;

        var logLevels = {
          CRITICAL: 50,
          ERROR: 40,
          WARNING: 30,
          VERBOSE: 15,
          DEBUG: 10,
          INFO: 20
        };

        $scope.scrollBottom = function() {
          // Delay for 1/2 second before scrolling
          if (angular.isDefined($scope.scrollTimeout)) {
            $timeout.cancel($scope.scrollTimeout);
          }
          $scope.scrollTimeout = $timeout(function () {
            if ($scope.autoScroll) {
              $scope.gridApi.core.scrollTo($scope.log[$scope.log.length - 1]);
            }
          }, 500);
        };

        $scope.updateGrid = function() {
          // Delay for 1 second before getting filtered results from server
          if (angular.isDefined($scope.filterTimeout)) {
            $timeout.cancel($scope.filterTimeout);
          }
          $scope.filterTimeout = $timeout(function () {
            getData()
          }, 1000);
        };

        var getData = function() {
          if ($scope.logStream) {
            $scope.logStream.abort();
          }

          $scope.log = [];
          $scope.gridOptions.data = $scope.log;

          var queryStr = '?lines=' + $scope.lines;

          for (var i = 0; i < $scope.gridApi.grid.columns.length; i++) {
            if ($scope.gridApi.grid.columns[i].filters[0].term) {
              var filterField = $scope.gridApi.grid.columns[i].field;
              var filterValue = $scope.gridApi.grid.columns[i].filters[0].term;
              queryStr = queryStr + '&' + filterField + '=' + filterValue;
            }
          }

          Oboe({
            url: '/api/server/log/' + queryStr,
            pattern: '{message}',
            start: function(stream) {
              $scope.logStream = stream;
            }
          }).then(function() {
            // finished loading
            $scope.logStream = false;
          }, function(error) {
            // handle errors
            $scope.logStream = false;
          }, function(node) {
            $scope.log.push(node);
            $scope.scrollBottom();
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
            {field: 'asctime', name: 'Time', cellFilter: 'date', enableSorting: true, width: 120},
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
            $scope.gridApi = gridApi;
            $scope.gridApi.core.on.filterChanged($scope, function() {
              $scope.updateGrid();
            });
            getData();
          }
        };

        // Cancel timer and stop the stream
        $scope.$on("$destroy", function() {
          if (angular.isDefined($scope.filterTimeout)) {
            $timeout.cancel($scope.filterTimeout);
          }
          if (typeof $scope.logStream !== 'undefined' && $scope.logStream) {
            $scope.logStream.abort();
          }
        });
      }]);