/* global angular */
(function () {
	'use strict';

	angular
		.module('plugins.execute')
		.component('executeView', {
			templateUrl: 'plugins/execute/execute.tmpl.html',
			controllerAs: 'vm',
			controller: executeController
		});

	function executeController($interval, executeService) {
		var vm = this;

		vm.$onInit = activate;
		vm.$onDestroy = destroy;
		vm.execute = execute;
		vm.stopStream = stopStream;
		vm.streaming = false;

		var taskInterval;

		function activate() {
			getRunning();

			taskInterval = $interval(getRunning, 3000);
		}

		function getRunning() {
            executeService.getQueue().then(function (data) {
                vm.running = data.tasks;
            });
        }

		function execute(options, tasks) {
			options.tasks = tasks;

			vm.options = options;
			vm.streaming = true;
		}

		function stopStream() {
			delete vm.options;
			vm.streaming = false;
		}

		function destroy() {
			$interval.cancel(taskInterval);
		}
	}
}());