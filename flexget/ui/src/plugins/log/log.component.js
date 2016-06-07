(function () {
	'use strict';

	angular
		.module('plugins.log')
		.component('logView', {
			//templateUrl: 'plugins/log/log.tmpl.html',
			//controllerAs: 'vm',
			//controller: logController
		});

	function logController($scope) {
		var vm = this;

		vm.logStream = false;

		vm.status = 'Connecting';

		vm.filter = {
			lines: 400,
			search: ''
		};

		vm.refreshOpts = {
			debounce: 1000
		};

		vm.toggle = function () {
			if (vm.status == 'Disconnected') {
				vm.refresh();
			} else {
				vm.stop();
			}
		};

		vm.clear = function () {
			vm.gridOptions.data = [];
		};

		vm.stop = function () {
			if (typeof vm.logStream !== 'undefined' && vm.logStream) {
				vm.logStream.abort();
				vm.logStream = false;
				vm.status = "Disconnected";
			}

		};

		vm.refresh = function () {
			// Disconnect existing log streams
			vm.stop();

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

		var rowTemplate = '<div class="{{ row.entity.log_level | lowercase }}"' +
			'ng-class="{summary: row.entity.message.startsWith(\'Summary\'), accepted: row.entity.message.startsWith(\'ACCEPTED\')}"><div ' +
			'ng-repeat="(colRenderIndex, col) in colContainer.renderedColumns track by col.uid" ' +
			'class="ui-grid-cell" ' +
			'ng-class="{ \'ui-grid-row-header-cell\': col.isRowHeader }"  ui-grid-cell>' +
			'</div></div>';

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
			rowTemplate: rowTemplate,
			onRegisterApi: function (gridApi) {
				vm.gridApi = gridApi;
				vm.refresh();
			}
		};

		// Cancel timer and stop the stream when navigating away
		$scope.$on("$destroy", function () {
			vm.stop();
		});
	}

})();