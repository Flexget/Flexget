(function () {
	'use strict';

	angular
		.module('plugins.execute')
		.component('executeView', {
			templateUrl: 'plugins/execute/execute.tmpl.html',
			controllerAs: 'vm',
			controller: executeController,
		});
				
	function executeController($scope, $interval, $q, executeService, $filter) {
		var vm = this;

		vm.$onInit = activate;
		vm.execute = execute;

		var taskInterval = $interval(getRunning, 3000);

		function activate() {
			getRunning();
		}

		function getRunning() {
            executeService.getQueue().then(function (data) {
                vm.running = data.tasks
            });
        };

		function execute(options, tasks) {
			console.log(options, tasks);
		}
	
		$scope.$on('$destroy', function () {
			$interval.cancel(taskInterval);
		});
	}
})();
		

		//allTasks = [];

       // vm.stream = { running: false, tasks: [] };
       /*
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

            var options = {};
            angular.copy(vm.options.settings, options);
            executeService.execute(vm.tasksInput.tasks, options)
                .log(function (log) {
                    console.log(log);
                })
                .progress(function (update) {
                    var filtered = $filter('filter')(vm.stream.tasks, { status: '!complete' });
                    angular.extend(filtered[0], update);
                    updateProgress();
                })
                .summary(function (update) {
                    var filtered = $filter('filter')(vm.stream.tasks, { status: 'complete' });
                    angular.extend(filtered[filtered.length - 1], update);
                    updateProgress();
                })
                .entry_dump(function (entries) {
                    var filtered = $filter('filter')(vm.stream.tasks, { status: 'complete' });
                    angular.extend(filtered[filtered.length - 1], { entries: entries });
                });
        };
 //   }

//})();*/