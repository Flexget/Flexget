'use strict';

var logViewModule = angular.module("logViewModule", ['ngOboe', 'ui.grid', 'ui.grid.autoResize']);

registerFlexModule(logViewModule);

logViewModule.controller('LogViewCtrl',
    ['$scope', '$timeout', '$filter', '$http', 'Oboe', 'uiGridConstants',
      function($scope, $timeout, $filter, $http, Oboe, uiGridConstants) {
        $scope.title = 'Server Log';

        $scope.log = [];
        $scope.logStream = false;

        $scope.lines = 400;
        $scope.message = "";
        $scope.task = "";
        $scope.taskSelected = "";
        $scope.taskSearch = "";
        $scope.autoScroll = true;
        $scope.logLevel = "INFO";
        $scope.logLevels = [
          'CRITICAL',
          'ERROR',
          'WARNING',
          'INFO',
          'VERBOSE',
          'DEBUG'
        ];

        $scope.filterTask = function(task) {
          $scope.task = task;
          $scope.updateGrid();
        };

        $http.get('/api/tasks/').
            success(function(data, status, headers, config) {
              // schema-form doesn't allow forms with an array at root level
              $scope.tasks = data.tasks;
            });

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

          var queryStr = '?lines=' + $scope.lines +
              '&levelname=' + $scope.logLevel +
              '&message=' + $scope.message +
              '&task=' + $scope.taskSearch;

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
          columnDefs: [
            {field: 'asctime', name: 'Time', cellFilter: 'date', enableSorting: true, width: 120},
            {field: 'levelname', name: 'Level', enableSorting: false, width: 65},
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