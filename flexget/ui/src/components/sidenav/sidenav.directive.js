(function () {
    'use strict';

    angular.module('flexget.components')
        .directive('sideNav', sideNavDirective);

    function sideNavDirective() {
        return {
            restrict: 'E',
            replace: 'true',
            templateUrl: 'components/sidenav/sidenav.tmpl.html',
            controllerAs: 'vm',
            controller: function ($mdMedia, sideNav) {
                var vm = this;
                vm.navItems = sideNav.items;
            }
        }
    }

})
();