(function () {
	'use strict';

	angular
		.module('plugins.log')
		.component('logView', {
			templateUrl: 'plugins/log/log.tmpl.html',
			controllerAs: 'vm',
			controller: logController
		});

	function logController($scope) {
		var vm = this;

		vm.logStream = false;
		vm.toggle = toggle;
		vm.clear = clear;
		vm.refresh = refresh;
		vm.$onDestroy = destroy;

		vm.status = 'Connecting';

		vm.filter = {
			lines: 400,
			search: ''
		};

		vm.refreshOpts = {
			debounce: 1000
		};

		function toggle() {
			if (vm.status == 'Disconnected') {
				vm.refresh();
			} else {
				stop();
			}
		};

		function clear() {
			vm.gridOptions.data = [];
		};

		function stop() {
			if (typeof vm.logStream !== 'undefined' && vm.logStream) {
				vm.logStream.abort();
				vm.logStream = false;
				vm.status = "Disconnected";
			}

		};

		function refresh() {
			// Disconnect existing log streams
			stop();

			vm.status = "Connecting";
			vm.gridOptions.data = [];

			var queryParams = '?lines=' + vm.filter.lines;
			if (vm.filter.search) {
				queryParams = queryParams + '&search=' + vm.filter.search;
			}

			vm.logStream = oboe({ url: '/api/server/log/' + queryParams })
				.start(function () {
					$scope.$applyAsync(function () {
						vm.status = "Streaming";
					});
				})
				.node('{message}', function (node) {
					$scope.$applyAsync(function () {
						vm.gridOptions.data.push(node);
					});
				})
				.fail(function (test) {
					$scope.$applyAsync(function () {
						vm.status = "Disconnected";
					});
				})
		};

		vm.gridOptions = {
			data: [],
			enableSorting: true,
			rowHeight: 20,
			columnDefs: [
				{ field: 'timestamp', name: 'Time', cellFilter: 'date', enableSorting: true, width: 120 },
				{ field: 'log_level', name: 'Level', enableSorting: false, width: 65 },
				{ field: 'plugin', name: 'Plugin', enableSorting: false, width: 80, cellTooltip: true },
				{ field: 'task', name: 'Task', enableSorting: false, width: 65, cellTooltip: true },
				{ field: 'message', name: 'Message', enableSorting: false, minWidth: 400, cellTooltip: true }
			],
			rowTemplate: "row-template.html",
			onRegisterApi: function (gridApi) {
				vm.gridApi = gridApi;
				vm.refresh();
			}
		};

		// Cancel timer and stop the stream when navigating away
		function destroy() {
			stop();
		};
	}

})();