/* global angular */
(function () {
    'use strict';

    angular
        .module('components.sidenav')
        .factory('sideNavService', sideNavService);

    function sideNavService($mdMedia, $mdSidenav, $rootScope) {
        return {
            toggle: toggle,
            close: close
        };

        function toggle() {
            if ($mdSidenav('left').isLockedOpen()) {
                $rootScope.menuMini = !$rootScope.menuMini;
            } else {
                $rootScope.menuMini = false;
                $mdSidenav('left').toggle();
            }
        }

        function close() {
            if (!$mdMedia('gt-lg')) {
                $mdSidenav('left').close();
            }
        }
    }
}());