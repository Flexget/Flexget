(function () {
	'use strict';
	
	angular
		.module("plugins.history")
		.component('historyView', {
			templateUrl: 'plugins/history/history.tmpl.html',
			controllerAs: 'vm',
			controller: historyController
		});

	function historyController(historyService) {
		var vm = this;

		vm.$onInit = activate;

		function activate() {
			getHistory();
		}

		function getHistory() {
			return historyService.getHistory().then(function (data) {
				vm.entries = data.entries;
			});
		}
	}
}());