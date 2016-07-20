/* global angular */
(function () {
	'use strict';

	angular
		.module('plugins.seen')
		.component('seenView', {
			templateUrl: 'plugins/seen/seen.tmpl.html',
			controllerAs: 'vm',
			controller: seenController
		});

	function seenController(seenService) {
		var vm = this;

		vm.$onInit = activate;

		function activate() {
			getSeen();
		}

		function getSeen() {
			return seenService.getSeen().then(function (data) {
				vm.entries = data.seen_entries;
			});
		}
	}
}());