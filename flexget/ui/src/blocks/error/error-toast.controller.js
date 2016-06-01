(function () {

	angular
		.module('blocks.error')
		.controller('errorToastController', errorToastController);

	function errorToastController($mdDialog, error) {
		var vm = this;

		vm.error = error;
		vm.openDetails = openDetails;

		var dialog = {
			template: '<error-dialog error="vm.error"></error-dialog>',
			locals: {
				error: error
			},
			bindToController: true,
			controllerAs: 'vm',
			controller: function () { }
		};

		function openDetails() {
			$mdDialog.show(dialog);
		};
	};
})();