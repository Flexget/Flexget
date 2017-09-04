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

    function sideNavController($rootScope, routerHelper, semver, sideNavService) {
        var vm = this;

        var allStates = routerHelper.getStates();
        vm.close = sideNavService.close;
        vm.$onInit = activate;
        vm.isSmallMenu = isSmallMenu;
        vm.hasUpdate = hasUpdate;

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

        function hasUpdate(current, latest) {
            return semver(vm.versions.latest_version, vm.versions.flexget_version) === 1;
        }

        function isSmallMenu() {
            return $rootScope.menuMini;
        }
    }
}());