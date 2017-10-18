/* global angular */
(function () {
    'use strict';

    angular
        .module('components.toolbar')
        .config(toolbarConfig);

    function toolbarConfig(toolbarHelperProvider) {
        var manageMenu = {
            type: 'menu',
            label: 'Manage',
            icon: 'cog',
            items: [],
            order: 255
        };

        //Register default Manage menu
        toolbarHelperProvider.registerItem(manageMenu);
    }
}());