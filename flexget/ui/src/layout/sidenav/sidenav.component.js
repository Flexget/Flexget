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

        //TODO: Move from sideNav service to router, mainly the items, not close function
        vm.navItems = routerHelper.getStates();

        console.log(vm.navItems);        
        
        //console.log(routerHelper.getStates);

       // vm.close = sideNav.close;
    }
})();