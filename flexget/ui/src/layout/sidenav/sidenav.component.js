(function () {
	'use strict';

	angular
		.module('flexget.layout')
		.component('sideNav', {
			templateUrl: 'layout/sidenav/sidenav.tmpl.html',
			controllerAs: 'vm',
			controller: sideNavController
		});

	function sideNavController(routerHelper) {
		var vm = this;
		
		var allStates = routerHelper.getStates();
		vm.$onInit = activate;

		function activate() {
			getNavRoutes();
		}

		function getNavRoutes() {
			vm.navItems = allStates.filter(function (r) {
				return r.settings && r.settings.weight;
			}).sort(function (r1, r2) {
				return r1.settings.weight - r2.settings.weight;
			});
		}
		
		
		//TODO: Implement functions again, the ones that make the collapsing etc work
		// vm.close = sideNav.close;
	}
})();