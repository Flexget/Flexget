/* global angular */
(function () {
    'use strict';

    angular
        .module('plugins.status')
        .config(statusConfig);

    function statusConfig(routerHelperProvider) {
        routerHelperProvider.configureStates(getStates());
    }

    function getStates() {
        return [
            {
                state: 'status',
                config: {
                    url: '/status',
                    component: 'status-view',
                    settings: {
                        weight: 7,
                        icon: 'heartbeat',
                        caption: 'Status'
                    }
                }
            }
        ];
    }
}());