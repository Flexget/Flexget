(function () {
    'use strict';

    angular.module('components.toolbar')
        .component('toolBar', {
            templateUrl: 'components/toolbar/toolbar.tmpl.html',
            controllerAs: 'vm',
            controller: toolbarController
        });

    function toolbarController(sideNavService) {
        var vm = this;
        
        vm.toggle = sideNavService.toggle;
       // vm.toolBarItems = toolBar.items;
    }

})();