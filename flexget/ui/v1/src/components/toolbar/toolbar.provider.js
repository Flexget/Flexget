/* global angular */
(function () {
    'use strict';

    angular
        .module('components.toolbar')
        .provider('toolbarHelper', toolbarHelperProvider);

    function toolbarHelperProvider() {
        var items = [];
        var defaultOrder = 128;

        this.registerItem = registerItem;
        this.$get = toolbarHelper;

        function registerItem(item) {
            switch (item.type) {
                case 'menu':
                    registerMenu(item);
                    break;

                case 'menuItem':
                    registerMenuItem(item);
                    break;

                case 'button':
                    registerButton(item);
                    break;

                default:
                    throw 'Unknown toolbar item type found: ' + item.type;
            }

            function registerButton(item) {
                if (!item.order) {
                    item.order = defaultOrder;
                }
                items.push(item);
            }

            function registerMenu(item) {
                // Ignore if menu already registered
                var existingMenu = getMenu(item.label);
                if (!existingMenu) {
                    if (!item.order) {
                        item.order = defaultOrder;
                    }
                    items.push(item);
                } else {
                    throw (new Error('Menu ' + item.label + ' has already been registered'));
                }
            }

            function registerMenuItem(item) {
                if (!item.order) {
                    item.order = defaultOrder;
                }

                var menu = getMenu(item.menu);
                if (menu) {
                    menu.items.push(item);
                } else {
                    throw (new Error('Unable to register menu item ' + item.label + ' as Menu ' + item.menu + ' was not found'));
                }
            }

            function getMenu(menu) {
                for (var i = 0, len = items.length; i < len; i++) {
                    var item = items[i];
                    if (item.type === 'menu' && item.label === menu) {
                        return item;
                    }
                }
            }
        }

        function toolbarHelper() {
            return {
                items: items
            };
        }
    }
} ());