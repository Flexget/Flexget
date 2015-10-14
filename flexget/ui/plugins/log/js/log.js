(function () {
  'use strict';

  var logViewModule = angular.module('logViewModule', ['ngOboe', 'ui.grid', 'ui.grid.autoResize']);

  registerModule(logViewModule);

  logViewModule.run(function(route, sideNav, toolBar, $state) {
    route.register('log', '/log', 'LogViewCtrl', 'plugin/log/static/index.html');
    sideNav.register('/log', 'Log', 'fa fa-file-text-o', 128);
    toolBar.registerButton('Log', 'fa fa-file-text-o', function(){$state.go('log')});
  });

  logViewModule.controller('LogViewCtrl',
    ['$scope', '$timeout', '$filter', '$http', 'Oboe', 'uiGridConstants',
      function ($scope, $timeout, $filter, $http, Oboe, uiGridConstants) {
        $scope.title = 'Server Log';

        var logItems = [];
        var logStream = false;

        $scope.status = 2;
        $scope.autoScroll = true;
        $scope.filter = {
          lines: 400,
          message: "",
          task: "",
          levelname: "INFO"
        };
        $scope.taskSearch = "";
        $scope.taskSelect = "";

        $scope.logLevels = [
          'CRITICAL',
          'ERROR',
          'WARNING',
          'INFO',
          'VERBOSE',
          'DEBUG'
        ];

        /* Abort log stream */
        $scope.abort = function () {
          if (angular.isDefined($scope.filterTimeout)) {
            $timeout.cancel($scope.filterTimeout);
          }
          if (typeof logStream !== 'undefined' && logStream) {
            logStream.abort();
            logStream = false;
            $scope.status = 2;
          }
        };

        /* Get a list of tasks for autocomplete filtering */
        $http.get('/api/tasks/').
          success(function (data, status, headers, config) {
            $scope.tasks = [];
            angular.forEach(data.tasks, function (value, key) {
              $scope.tasks.push(value.name)
            });

          });

        $scope.filterTask = function (task) {
          $scope.filter.task = task;
          $scope.updateGrid();
        };

        $scope.scrollBottom = function () {
          // Delay for 500 ms before scrolling
          if (angular.isDefined($scope.scrollTimeout)) {
            $timeout.cancel($scope.scrollTimeout);
          }
          $scope.scrollTimeout = $timeout(function () {
            if ($scope.autoScroll) {
              $scope.gridApi.core.scrollTo(logItems[logItems.length - 1]);
            }
          }, 500);
        };

        $scope.updateGrid = function () {
          // Delay for 1 second before getting filtered results from server
          if (angular.isDefined($scope.filterTimeout)) {
            $timeout.cancel($scope.filterTimeout);
          }
          $scope.filterTimeout = $timeout(function () {
            getLogData()
          }, 1000);
        };

        var getLogData = function () {
          if (logStream) {
            logStream.abort();
          }

          $scope.status = 1;

          logItems = [];
          $scope.gridOptions.data = logItems;

          var count = 0;
          var queryStr;

          angular.forEach($scope.filter, function (value, key) {
            if (value) {
              if (count == 0) {
                queryStr = "?" + key + "=" + value
              } else {
                queryStr = queryStr + "&" + key + "=" + value
              }
              count++;
            }
          });

          Oboe({
            url: '/api/server/log/' + queryStr,
            pattern: '{message}',
            start: function (stream) {
              logStream = stream;
            }
          }).then(function () {
            $scope.status = 2;
          }, function (error) {
            $scope.status = 2;
          }, function (node) {
            $scope.status = 0;
            logItems.push(node);
            $scope.scrollBottom();
          });
        };

        var rowTemplate = function () {
          return '<div class="{{ row.entity.levelname | lowercase }}"' +
            'ng-class="{summary: row.entity.message.startsWith(\'Summary\'), accepted: row.entity.message.startsWith(\'ACCEPTED\')}"><div ' +
            'ng-repeat="(colRenderIndex, col) in colContainer.renderedColumns track by col.uid" ' +
            'class="ui-grid-cell" ' +
            'ng-class="{ \'ui-grid-row-header-cell\': col.isRowHeader }"  ui-grid-cell>' +
            '</div></div>'
        };

        $scope.gridOptions = {
          data: logItems,
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
          onRegisterApi: function (gridApi) {
            $scope.gridApi = gridApi;
            $scope.gridApi.core.on.filterChanged($scope, function () {
              $scope.updateGrid();
            });
            getLogData();
          }
        };

        // Cancel timer and stop the stream when navigating away
        $scope.$on("$destroy", function () {
          $scope.abort();
        });
      }]);
})();