(function () {
    'use strict';

    angular
		.module('components.toolbar')
        .component('toolBar', {
            templateUrl: 'components/toolbar/toolbar.tmpl.html',
            controllerAs: 'vm',
            controller: toolbarController
        });

    function toolbarController(sideNavService, toolBarService) {
        var vm = this;
        
		vm.$onInit = activate;
        vm.toggle = sideNavService.toggle;

		function activate() {
			vm.toolBarItems = toolBarService.items;
		}
    }

}());