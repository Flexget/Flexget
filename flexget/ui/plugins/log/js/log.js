(function () {
  'use strict';

  var logViewModule = angular.module('logViewModule', ['ui.grid', 'ui.grid.autoResize', 'ui.grid.autoScroll']);
  registerModule(logViewModule);

  logViewModule.run(function(route, sideNav, toolBar, $state) {
    route.register('log', '/log', 'LogViewCtrl', 'plugin/log/static/index.html');
    sideNav.register('/log', 'Log', 'fa fa-file-text-o', 128);
    toolBar.registerButton('Log', 'fa fa-file-text-o', function(){$state.go('log')});
  });

  logViewModule.controller('LogViewCtrl', function ($scope, $timeout, uiGridConstants) {
    var filterTimeout, newDataTimeout;
    var logStream = false;

    $scope.status = 'Connecting';
    $scope.lines = 400;
    $scope.search = '';

    $scope.toggleStream = function() {
      if ($scope.status == "Disconnected") {
        $scope.updateGrid();
      } else {
        abort();
      }
    };

    $scope.updateGrid = function () {
      // Delay for 1 second before getting search results from server
      if (angular.isDefined(filterTimeout)) {
        $timeout.cancel(filterTimeout);
      }
      filterTimeout = $timeout(function () {
        getLogData()
      }, 1000);
    };

    var abort = function () {
      if (angular.isDefined(filterTimeout)) {
        $timeout.cancel(filterTimeout);
      }
      if (typeof logStream !== 'undefined' && logStream) {
        logStream.abort();
        logStream = false;
        $scope.status = "Disconnected";
      }
    };

    var getLogData = function () {
      // Disconnect existing log streams
      abort();

      $scope.status = "Connecting";
      $scope.gridOptions.data = [];

      var queryParams = '?lines=' + $scope.lines;
      if ($scope.search) {
        queryParams = queryParams + '&search=' + $scope.search;
      }

      logStream = oboe({url: '/api/server/log/' + queryParams})
        .start(function () {
          $scope.$applyAsync(function () {
            $scope.status = "Streaming";
          });
        })
        .node('{message}', function(node) {
          $scope.$applyAsync(function () {
            $scope.gridOptions.data.push(node);
          });
        })
        .fail(function (test){
          $scope.$applyAsync(function () {
            $scope.status = "Disconnected";
          });
        })
    };

    var rowTemplate = '<div class="{{ row.entity.levelname | lowercase }}"' +
      'ng-class="{summary: row.entity.message.startsWith(\'Summary\'), accepted: row.entity.message.startsWith(\'ACCEPTED\')}"><div ' +
      'ng-repeat="(colRenderIndex, col) in colContainer.renderedColumns track by col.uid" ' +
      'class="ui-grid-cell" ' +
      'ng-class="{ \'ui-grid-row-header-cell\': col.isRowHeader }"  ui-grid-cell>' +
      '</div></div>';

    $scope.gridOptions = {
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
        $scope.gridApi = gridApi;
        getLogData();
      }
    };

    // Cancel timer and stop the stream when navigating away
    $scope.$on("$destroy", function () {
      abort();
    });
  });

})();