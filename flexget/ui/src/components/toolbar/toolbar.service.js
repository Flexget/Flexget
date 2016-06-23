(function () {
    'use strict';

    angular.module('components.toolbar')
        .factory('toolBarService', toolbarService);

    function toolbarService() {
        // Add default Manage (cog) menu
        var items = [
            {type: 'menu', label: 'Manage', cssClass: 'fa fa-cog', items: [], width: 2, order: 255}
        ];

        var defaultOrder = 128;

        var getMenu = function (menu) {
            for (var i = 0, len = items.length; i < len; i++) {
                var item = items[i];
                if (item.type == 'menu' && item.label == menu) {
                    return item;
                }
            }
        };

        return {
            items: items,
            registerButton: function (label, cssClass, action, order) {
                if (!order) {
                    order = defaultOrder;
                }
                items.push({type: 'button', label: label, cssClass: cssClass, action: action, order: order});
            },
            registerMenu: function (label, cssClass, width, order) {
                // Ignore if menu already registered
                var existingMenu = getMenu(label);
                if (!existingMenu) {
                    if (!order) {
                        order = defaultOrder;
                    }
                    if (!width) {
                        width = 2;
                    }
                    items.push({type: 'menu', label: label, cssClass: cssClass, items: [], width: 2, order: order});
                }
            },
            registerMenuItem: function (menu, label, cssClass, action, order) {
                if (!order) {
                    order = defaultOrder;
                }

                menu = getMenu(menu);
                if (menu) {
                    menu.items.push({label: label, cssClass: cssClass, action: action, order: order});
                } else {
                    throw 'Unable to register menu item ' + label + ' as Menu ' + menu + ' was not found';
                }
            }
        }
    }

})();