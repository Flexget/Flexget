/* global angular */
(function () {
    'use strict';

    angular
        .module('components.sidenav')
        .component('sideNav', {
            templateUrl: 'components/sidenav/sidenav.tmpl.html',
            controllerAs: 'vm',
            controller: sideNavController
        });

    function sideNavController($rootScope, routerHelper, sideNavService) {
        var vm = this;

        var allStates = routerHelper.getStates();
        vm.close = sideNavService.close;
        vm.$onInit = activate;
        vm.isSmallMenu = isSmallMenu;

        function activate() {
            getNavRoutes();
            getVersionInfo();
        }

        function getNavRoutes() {
            vm.navItems = allStates.filter(function (r) {
                return r.settings && r.settings.weight;
            }).sort(function (r1, r2) {
                return r1.settings.weight - r2.settings.weight;
            });
        }

        function getVersionInfo() {
            sideNavService.getVersionInfo().then(function (data) {
                vm.versions = data;
            });
        }

        function isSmallMenu() {
            return $rootScope.menuMini;
        }
    }
}());