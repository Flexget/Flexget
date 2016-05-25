(function () {
    'use strict';

    angular.module('flexget.layout')
        .factory('sideNav', sideNavService);

    function sideNavService($rootScope, $mdSidenav, $mdMedia) {
        var items = [];

        var toggle = function () {
            if ($mdSidenav('left').isLockedOpen()) {
                $rootScope.menuMini = !$rootScope.menuMini;
            } else {
                $rootScope.menuMini = false;
                $mdSidenav('left').toggle();
            }
        };

        var close = function () {
            if (!$mdMedia('gt-lg')) {
                $mdSidenav('left').close();
            }
        };

        return {
            toggle: toggle,
            close: close,
            register: function (href, caption, icon, order) {
                href = '#' + href;
                items.push({href: href, caption: caption, icon: icon, order: order})
            },
            items: items
        }
    }

})();


