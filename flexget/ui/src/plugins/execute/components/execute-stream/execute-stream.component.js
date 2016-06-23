(function () {
	'use strict';

	angular
		.module('plugins.execute')
		.component('executeStream', {
			templateUrl: 'plugins/execute/components/execute-stream/execute-stream.tmpl.html',
			controllerAs: 'vm',
			controller: executeStreamController,
			bindings: {
				running: '<',
				stopStream: '<',
				options: '<'
				//stream: '<',
				//clear: '<'
			},
		});
	
	function executeStreamController(executeService) {
		var vm = this;

		vm.$onInit = activate;
		vm.clear = clear;

		function activate() {
			setupTaskProperties();
			console.log('activate');
			//TODO: Start stream
		}

		function setupTaskProperties() {
			for (var i = 0; i < vm.options.tasks.length; i++) {
				var task = {
					name: vm.options.tasks[i],
					percent: 0,
					entries: [],
					status: 'pending'
				}

				vm.options.tasks[i] = task;
			}
		}

		function clear() {
			vm.stopStream();
		}

		function updateProgress() {
			var totalPercent = 0;
			for (var i = 0; i < vm.stream.tasks.length; i++) {
				totalPercent = totalPercent + vm.stream.tasks[i].percent;
			}
			vm.stream.percent = totalPercent / vm.stream.tasks.length;
		};
 
		/*executeService.execute(vm.tasksInput.tasks, options)
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
			});*/
	}
})();