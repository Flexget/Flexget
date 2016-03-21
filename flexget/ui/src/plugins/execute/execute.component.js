(function () {
    'use strict';

    angular
      .module('flexget.plugins.execute')
        .component('executeView', {
          templateUrl: 'plugins/execute/execute.tmpl.html',
          controllerAs: 'vm',
          controller: executeController,
        });

    function executeController($scope, $interval, $q, tasks) {
        var vm = this,
            allTasks = [];

        vm.stream = {running: false, tasks: []};
        vm.options = {
            isOpen: false,
            settings: {
                log: true,
                entry_dump: true,
                progress: true,
                summary: true,
                now: true
            },
            optional: [
                {name: 'test', value: false, help: '......', display: 'Test Mode'},
                {name: 'no-cache', value: false, help: 'disable caches. works only in plugins that have explicit support', display: 'Caching'},
                {name: 'stop-waiting', value: null, help: 'matches are not downloaded but will be skipped in the future', display: 'Waiting'},
                {name: 'learn', value: null, help: 'matches are not downloaded but will be skipped in the future', display: 'Learn'},
                {name: 'disable-tracking', value: null, help: 'disable episode advancement for this run', display: 'Tracking'},
                {name: 'discover-now', value: null, help: 'immediately try to discover everything', display: 'Discover'}
            ],
            toggle: function(option) {
                option.value = !option.value;
            }
        };

        // Get a list of tasks for auto complete
        tasks.list()
            .then(function (tasks) {
                allTasks = tasks;
            });

        vm.addTask = function (chip) {
            var chipLower = chip.toLowerCase();

            function alreadyAdded(newChip) {
                for (var i = 0; i < vm.tasksInput.tasks.length; i++) {
                    if (newChip.toLowerCase() == vm.tasksInput.tasks[i].toLowerCase()) {
                        return true
                    }
                }
                return false;
            }

            if (chip.indexOf('*') > -1) {
                for (var i = 0; i < allTasks.length; i++) {
                    var match = new RegExp("^" + chip.replace("*", ".*") + "$", 'i').test(allTasks[i]);
                    if (match && !alreadyAdded(allTasks[i])) {
                        vm.tasksInput.tasks.push(allTasks[i]);
                    }
                }
                return null;
            }

            for (var i = 0; i < allTasks.length; i++) {
                if (chipLower == allTasks[i].toLowerCase() && !alreadyAdded(allTasks[i])) {
                    return chip;
                }
            }
            return null;
        };
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

        vm.clear = function () {
            vm.stream.tasks = [];
            vm.stream.running = false;
            vm.options.tasks = [];
        };

        vm.execute = function () {
            vm.stream.running = true;
            vm.stream.tasks = [];

            angular.forEach(vm.tasksInput.tasks, function (task) {
                vm.stream.tasks.push({
                    status: 'pending',
                    name: task,
                    entries: [],
                    percent: 0
                });
            });

            var updateProgress = function () {
                var totalPercent = 0;
                for (var i = 0; i < vm.stream.tasks.length; i++) {
                    totalPercent = totalPercent + vm.stream.tasks[i].percent;
                }
                vm.stream.percent = totalPercent / vm.stream.tasks.length;
            };

            var getTask = function (name) {
                for (var i = 0; i < vm.stream.tasks.length; i++) {
                    var task = vm.stream.tasks[i];
                    if (task.name == name) {
                        return task
                    }
                }
            };

            var streamTask = function (name) {
                var task = getTask(name);

                var options = {};
                angular.copy(vm.options.settings, options);
                angular.forEach(vm.options.optional, function (setting) {
                    //options[setting.name] = setting.value;
                });

                return tasks.execute(name, options)
                    .log(function (log) {
                        task.log.push(log);
                    })
                    .progress(function (update) {
                        angular.extend(task, update);
                        updateProgress();
                    })
                    .summary(function (update) {
                        angular.extend(task, update);
                        updateProgress();
                    })
                    .entry_dump(function (entries) {
                        task.entries = entries;
                    });
            };

            var done = vm.tasksInput.tasks.reduce(function (previous, taskName) {
                return previous.then(function () {
                    if (vm.stream.running) {
                        return streamTask(taskName);
                    }
                });
            }, $q.when());

            done.then(function () {
                vm.stream.running = false;
                vm.stream.percent = 100;
            });


        };

        var getRunning = function () {
            tasks.queue().then(function (tasks) {
                vm.running = tasks
            })
        };
        getRunning();
        var taskInterval = $interval(getRunning, 3000);

        // Cancel timer and stop the stream when navigating away
        $scope.$on("$destroy", function () {
            $interval.cancel(taskInterval);
            if (angular.isDefined(stream)) {
                stream.abort();
            }
        });
    }

})();
