(function () {
  'use strict';

  var executeModule = angular.module("executeModule", ['ui.grid', 'ui.grid.autoResize', 'angular-spinkit', 'flexget.services']);

  registerModule(executeModule);

  executeModule.run(function(route, sideNav) {
    route.register('execute', '/execute', 'ExecuteCtrl', 'plugin/execute/static/index.html');
    sideNav.register('/execute', 'Execute', 'fa fa-cog', 128);
  });

  executeModule.controller('ExecuteCtrl', function ($scope, $log, tasks) {

    // Used to calculate the precent complete of a running task
    var phasePercents = {
      input: 5,
      metainfo: 10,
      filter: 30,
      download: 50,
      modify: 65,
      output: 95
    };

    var allTasks = [];
    tasks.list()
      .then(function(tasks) {
        allTasks = tasks
      });

    $scope.executeTasks = [];
    $scope.searchText = [];
    $scope.queryTasks = function(query) {
      var taskFilter = function() {
        var lowercaseQuery = angular.lowercase(query);
        return function filterFn(task) {
          return (angular.lowercase(task).indexOf(lowercaseQuery) > -1);
        };
      };
      var result = query ? allTasks.filter(taskFilter()) : [];
      return result
    };

    $scope.clear = function() {
      $scope.stream = false;
    };

    $scope.run = function() {
      $scope.stream = {
        tasks: [],
        log: [],
        percentComplete: 0
      };

      var stream = tasks.executeStream($scope.executeTasks)
        .start(function() {
          //
        })
        .done(function() {
          $scope.stream.percentComplete = 100;
        })
        .tasks(function(tasks) {
          angular.forEach(tasks, function(task) {
            $scope.stream.tasks.push({
              id: task.id,
              name: task.name,
              percentComplete: 0,
              entries: {}
            });
          });
        })
        .log(function(log) {
          $scope.stream.log.push(log);
        })
        .progress(function(taskId, update) {
          var task = getTask(taskId);
          angular.extend(task, update);

          if (task['phase'] in phasePercents) {
            task.percentComplete = phasePercents[task['phase']];
          }
          if(['complete', 'aborted'].indexOf(task.status) >= 0) {
            task.percentComplete = 100;
          }

          updateProgress();
        })
        .entry(function(taskId, entry) {
          var task = getTask(taskId);
          task.entries[entry.url] = entry;
        });

      var getTask = function(taskId) {
        for (var i = 0; i < $scope.stream.tasks.length; i++) {
          var task = $scope.stream.tasks[i];
          if (task.id == taskId) {
            return task
          }
        }
      };

      var updateProgress = function() {
        var totalPercent = 0, totalTasks = 0;
        angular.forEach($scope.stream.tasks, function(task) {
          totalPercent = totalPercent + task.percentComplete;
          totalTasks++;
        });
        $scope.stream.percentComplete = totalPercent / totalTasks;
      }
    };

  });

})();