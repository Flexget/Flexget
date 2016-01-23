(function () {
    'use strict';

    angular.module('flexget.components')
        .factory('sideNav', sideNavService);

    function sideNavService($mdSidenav, $mdMedia) {
        var items = [];
        var menuMini = false;

        var toggle = function () {
            if ($mdSidenav('left').isLockedOpen()) {
                menuMini = !menuMini;
            } else {
                menuMini = false;
                $mdSidenav('left').toggle();
            }
        };

        var close = function () {
            if (!$mdMedia('gt-lg')) {
                $mdSidenav('left').close();
            }
        };

        return {
            mini: menuMini,
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


