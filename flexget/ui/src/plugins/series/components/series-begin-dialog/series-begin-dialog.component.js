(function () {

	angular
		.module('plugins.series')
		.component('seriesBeginDialog', {
			templateUrl: 'plugins/series/components/series-begin-dialog/series-begin-dialog.tmpl.html',
			controller: seriesBeginDialogController,
			controllerAs: 'vm',
			bindings: {
				show: '<'
			}
		});

	function seriesBeginDialogController($mdDialog, seriesService) {
		var vm = this;
		
		vm.cancel = cancel;
		vm.$onInit = activate;
		vm.saveBegin = saveBegin;
		
		function activate() {
			vm.begin = vm.show.begin_episode.episode_identifier;
			vm.originalBegin = angular.copy(vm.begin);
		}

		function cancel() {
			$mdDialog.cancel();
		}

		function saveBegin() {
			//TODO: Error handling
			var params = {
				episode_identifier: vm.begin
			}

			seriesService.updateShow(vm.show, params).then(function (data) {
				$mdDialog.hide(vm.begin);
			});
		}
	}
})();