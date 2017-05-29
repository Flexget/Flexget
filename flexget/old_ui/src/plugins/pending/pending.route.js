/* global angular */
(function () {
    'use strict';

    angular
        .module('plugins.pending')
        .config(pendingConfig);

    function pendingConfig(routerHelperProvider) {
        routerHelperProvider.configureStates(getStates());
    }

    function getStates() {
        return [
            {
                state: 'pending',
                config: {
                    url: '/pending',
                    component: 'pending-view',
                    settings: {
                        weight: 3,
                        icon: 'check',
                        caption: 'Pending'
                    }
                }
            }
        ];
    }
}());
