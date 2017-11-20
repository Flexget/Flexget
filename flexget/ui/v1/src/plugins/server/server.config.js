/* global angular */
(function () {
    'use strict';

    angular
        .module('plugins.server')
        .config(serverConfig);

    function serverConfig(serverServiceProvider, toolbarHelperProvider) {
        var serverService = serverServiceProvider.$get();
        var reloadButton = {
            menu: 'Manage',
            type: 'menuItem',
            label: 'Reload',
            icon: 'refresh',
            action: serverService.reload,
            order: 127
        };

        var shutdownButton = {
            menu: 'Manage',
            type: 'menuItem',
            label: 'Shutdown',
            icon: 'power-off',
            action: serverService.shutdown,
            order: 128
        };

        toolbarHelperProvider.registerItem(reloadButton);
        toolbarHelperProvider.registerItem(shutdownButton);
    }
}());