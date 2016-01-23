(function () {
    'use strict';

    angular.module('flexget.components').run(sideNavConfig);

    function sideNavConfig($rootScope, $mdSidenav, $mdMedia) {
        $rootScope.toggleNav = function () {
            if ($mdSidenav('left').isLockedOpen()) {
                $rootScope.menuMini = !$rootScope.menuMini;
            } else {
                $rootScope.menuMini = false;
                $mdSidenav('left').toggle();
            }
        };

        $rootScope.closeNav = function () {
            if (!$mdMedia('gt-lg')) {
                $mdSidenav('left').close();
            }
        };
    }

})();