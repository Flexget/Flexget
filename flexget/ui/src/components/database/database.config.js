/* global angular */
(function () {
    'use strict';

    angular
        .module('components.database')
        .config(databaseConfig);
    
    function databaseConfig(toolbarHelperProvider, databaseServiceProvider) {
        var databaseService = databaseServiceProvider.$get();
        var databaseToggle = {
            menu: 'Manage',
            type: 'menuItem',
            label: 'Database',
            icon: 'database',
            action: databaseService.toggle,
            order: 250
        };

         toolbarHelperProvider.registerItem(databaseToggle);
    }
}());