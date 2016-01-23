(function () {
    'use strict';

    angular.module('flexget.components')
        .directive('sideNav', sideNavDirective);

    function sideNavDirective() {
        return {
            restrict: 'E',
            replace: 'true',
            templateUrl: 'components/sidenav/sidenav.tmpl.html',
            controller: function ($scope, $mdMedia, sideNav) {
                $scope.navItems = sideNav.items;
            }
        }

    }

})
();