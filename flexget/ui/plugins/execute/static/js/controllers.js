'use strict';

var executeModule = angular.module("executeModule", ['ngOboe', 'ui.grid', 'ui.grid.autoResize']);

registerFlexModule(executeModule);


executeModule.controller('ExecuteCtrl', ['$scope', 'Oboe', function($scope, Oboe) {
  $scope.title = 'Execution';
  $scope.description = 'test123';
}]);


executeModule.controller('ExecuteLogCtrl',
  ['$scope', '$filter', 'Oboe', 'uiGridConstants',
    function($scope, $filter, Oboe, uiGridConstants) {
      var logStream;
      $scope.log = [];

      Oboe({
        url: '/api/server/log/?lines=400',
        pattern: '{message}',
        start: function(stream) {
          logStream = stream;
        }
      }).then(function() {
        // finished loading
      }, function(error) {
        // handle errors
      }, function(node) {
        $scope.log.push(node);
      });

      $scope.$on("$destroy", function() {
        if (logStream) {
          logStream.abort();
        }
      });

      var convertLogLevel = function (loglevel) {
        var level = 20;
        switch (loglevel) {
          case "CRITICAL":
            level = 50;
            break;
          case "ERROR":
            level = 40;
            break;
          case "WARNING":
            level = 30;
            break;
          case "VERBOSE":
            level = 15;
            break;
          case "DEBUG":
            level = 10;
            break;
        }
        return level
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
          {field: 'asctime', name: 'Time', cellFilter: 'date', enableSorting: true, width: 100},
          {field: 'levelname', name: 'Level', enableSorting: false, width: 100,
            filter: {
              type: uiGridConstants.filter.SELECT,
              selectOptions: [
                {value: 40, label: 'ERROR'},
                {value: 30, label: 'WARNING'},
                {value: 20, label: 'INFO'},
                {value: 15, label: 'VERBOSE'},
                {value: 10, label: 'DEBUG'}
              ],
              condition: function(level, cellValue) {
                return convertLogLevel(cellValue) >= level;
              }
            }
          },
          {field: 'name', name: 'Name', enableSorting: false, width: 100, cellTooltip: true},
          {field: 'task', name: 'Task', enableSorting: false, width: 60, cellTooltip: true},
          {field: 'message', name: 'Message', enableSorting: false, width: '*', cellTooltip: true},

        ],
        rowTemplate: rowTemplate()

      }

    }]);


executeModule.controller('ExecuteHistoryCtrl', ['$scope', 'Oboe', function($scope, Oboe) {
  $scope.title = 'Execution History';
  $scope.description = 'test123';
}]);