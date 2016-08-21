/* global angular */
(function () {
    'use strict';

    angular
        .module('plugins.config')
        .config(configConfig);

    function configConfig(routerHelperProvider, toolbarHelperProvider, $stateProvider) {
        routerHelperProvider.configureStates(getStates());

        var $state = $stateProvider.$get();

        var configButton = {
            type: 'button',
            label: 'Config',
            icon: 'pencil',
            action: goToRoute,
            order: 1
        };

        function goToRoute() {
            $state.go('flexget.config');
        }

        toolbarHelperProvider.registerItem(configButton);
    }

    function getStates() {
        return [
            {
                state: 'config',
                config: {
                    url: '/config',
                    component: 'config-view',
                    settings: {
                        weight: 3,
                        icon: 'pencil',
                        caption: 'Config'
                    }
                }
            }
        ];
    }
}());