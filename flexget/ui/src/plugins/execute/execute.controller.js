(function () {
    'use strict';

    angular.module("flexget.plugins.execute")
        .controller('executeController', executeController);

    function executeController($scope, tasks) {
        var vm = this, stream, allTasks = [];

        vm.options = {
            learn: false,
            noCache: false,
            stopWaiting: false,
            tracking: false,
            now: false,
            tail: false
        };

        // Get a list of tasks for auto complete
        tasks.list()
            .then(function (tasks) {
                allTasks = tasks
            });

        // Used for input form to select tasks to execute
        vm.tasksInput = {
            tasks: [],
            search: [],
            query: function (query) {
                var filter = function () {
                    var lowercaseQuery = angular.lowercase(query);
                    return function filterFn(task) {
                        return (angular.lowercase(task).indexOf(lowercaseQuery) > -1);
                    };
                };
                return query ? allTasks.filter(filter()) : [];
            }
        };

        var getRunning = function () {
            tasks.queue().then(function (tasks) {
                vm.running = tasks
            })
        };
        getRunning();

        vm.clear = function () {
            getRunning();
            vm.stream = false;
        };

        vm.execute = function () {
            vm.stream = {
                tasks: [],
                log: []
            };

            getRunning();

            stream = tasks.executeStream(vm.tasksInput.tasks)
                .start(function () {
                    //
                })
                .done(function () {
                    vm.stream.percent = 100;
                })
                .tasks(function (tasks) {
                    angular.forEach(tasks, function (task) {
                        vm.stream.tasks.push({
                            id: task.id,
                            status: 'pending',
                            name: task.name,
                            entries: {},
                            percent: 0
                        });
                    });
                })
                .log(function (log) {
                    vm.stream.log.push(log);
                })
                .progress(function (taskId, update) {
                    var task = getTask(taskId);
                    angular.extend(task, update);
                    updateProgress();
                })
                .summary(function (taskId, update) {
                    var task = getTask(taskId);
                    angular.extend(task, update);
                    updateProgress();
                })
                .entry_dump(function (taskId, entries) {
                    var task = getTask(taskId);
                    task.entries = entries;
                });

            var getTask = function (taskId) {
                for (var i = 0; i < vm.stream.tasks.length; i++) {
                    var task = vm.stream.tasks[i];
                    if (task.id == taskId) {
                        return task
                    }
                }
            };

            var updateProgress = function () {
                var totalPercent = 0;
                for (var i = 0; i < vm.stream.tasks.length; i++) {
                    totalPercent = totalPercent + vm.stream.tasks[i].percent;
                }
                vm.stream.percent = totalPercent / vm.stream.tasks.length;
            }
        };

        // Cancel timer and stop the stream when navigating away
        $scope.$on("$destroy", function () {
            if (angular.isDefined(stream)) {
                stream.abort();
            }
        });
    }

})();