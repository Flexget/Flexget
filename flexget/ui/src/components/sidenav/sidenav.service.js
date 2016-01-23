(function () {
    'use strict';

    angular.module('flexget.components')
        .factory('sideNav', sideNavService);

    function sideNavService() {
        var items = [];

        return {
            register: function (href, caption, icon, order) {
                href = '#' + href;
                items.push({href: href, caption: caption, icon: icon, order: order})
            },
            items: items
        }
    }

})();


