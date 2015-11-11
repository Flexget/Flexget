(function () {
  'use strict';

  var executeModule = angular.module("executeModule", ['ui.grid', 'ui.grid.autoResize', 'angular-spinkit', 'flexget.services']);

  registerModule(executeModule);

  executeModule.run(function(route, sideNav) {
    route.register('execute', '/execute', 'ExecuteCtrl', 'plugin/execute/static/index.html');
    sideNav.register('/execute', 'Execute', 'fa fa-cog', 128);
  });

  executeModule.filter('executePhaseFilter', function() {
    var phaseDescriptions = {
      input: "Gathering Entries",
      metainfo: "Figuring out meta data",
      filter: "Filtering Entries",
      download: "Downloading Accepted Entries",
      modify: "Modifying Entries",
      output: "Executing Outputs",
      exit: "Finished"
    };

    return function(phase) {
      if (phase in phaseDescriptions) {
        return phaseDescriptions[phase]
      } else {
        return "Processing"
      }
    };
  });

  executeModule.controller('ExecuteCtrl', function ($scope, $log, tasks) {

    var stream, allTasks = [];

    // Get a list of tasks for auto complete
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
      return query ? allTasks.filter(taskFilter()) : [];
    };

    $scope.clear = function() {
      $scope.stream = false;
    };

    $scope.run = function() {
      $scope.stream = {
        tasks: [],
        log: []
      };

      stream = tasks.executeStream($scope.executeTasks)
        .start(function() {
          //
        })
        .done(function() {
          $scope.stream.percent = 100;
        })
        .tasks(function(tasks) {
          angular.forEach(tasks, function(task) {
            $scope.stream.tasks.push({
              id: task.id,
              status: 'pending',
              name: task.name,
              entries: {},
              percent: 0
            });
          });
        })
        .log(function(log) {
          $scope.stream.log.push(log);
        })
        .progress(function(taskId, update) {
          var task = getTask(taskId);
          angular.extend(task, update);
          updateProgress();
        })
        .summary(function(taskId, update) {
          var task = getTask(taskId);
          angular.extend(task, update);
          updateProgress();
        })
        .entry_dump(function(taskId, entries) {
          var task = getTask(taskId);
          task.entries = entries;
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
        var totalPercent = 0;
        for (var i = 0; i < $scope.stream.tasks.length; i++) {
          totalPercent = totalPercent + $scope.stream.tasks[i].percent;
        }
        $scope.stream.percent = totalPercent / $scope.stream.tasks.length;
      }
    };

    // Cancel timer and stop the stream when navigating away
    $scope.$on("$destroy", function () {
      if (angular.isDefined(stream)) {
        stream.abort();
      }
    });
  });
})();