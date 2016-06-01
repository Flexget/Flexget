(function () {
    'use strict';

    angular.module('blocks.error')
        .factory('errorService', errorService);

    function errorService($mdToast, $mdDialog, $rootElement) {
		//TODO: Check if later on this can be converted to a component, right now this is not possible with ngMaterial
		var toast = {
			templateUrl: "blocks/error/error-toast.tmpl.html",
			position: "bottom right",
			controller: 'errorToastController',
			controllerAs: 'vm',
			hideDelay: 5000
		};

		var service = {
			showToast: showToast
		};
		return service;

		function showToast(error) {
			toast.locals = {
				error: error
			};
			
			$mdToast.show(toast);
		};
	};
})();