/* global angular */
(function () {
    'use strict';

    angular
        .module('plugins.execute')
        .config(executeConfig);

    function executeConfig(routerHelperProvider) {
        routerHelperProvider.configureStates(getStates());
    }

    function getStates() {
        return [
            {
                state: 'execute',
                config: {
                    url: '/execute',
                    component: 'execute-view',
                    settings: {
                        weight: 2,
                        icon: 'cog',
                        caption: 'Execute'
                    }
                }
            }
        ];
    }
}());