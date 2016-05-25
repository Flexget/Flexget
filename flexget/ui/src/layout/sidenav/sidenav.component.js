(function () {
    'use strict';

    angular
        .module('flexget.layout')
        .component('sideNav', {
            templateUrl: 'layout/sidenav/sidenav.tmpl.html',
            controllerAs: 'vm',
            controller: sideNavController
        });

    function sideNavController(sideNav) {
        var vm = this;

        //TODO: Move from sideNav service to router, mainly the items, not close function        
        vm.navItems = sideNav.items;
        vm.close = sideNav.close;
    }
})();