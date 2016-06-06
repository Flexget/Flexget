(function () {
	'use strict';

	angular
		.module('flexget.plugins.movies')
		.controller('newListController', newListController);

	function newListController(moviesService, $mdDialog) {
		var vm = this;

		vm.saveList = saveList;
		vm.cancel = cancel;

		function cancel() {
			$mdDialog.cancel();
		};

		function saveList() {
			moviesService.createList(vm.listName).then(function (newList) {
				$mdDialog.hide(newList);
			});
		}
	};
});