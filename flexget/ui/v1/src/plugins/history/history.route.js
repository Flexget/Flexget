/* global angular */
(function () {
    'use strict';

    angular
        .module('plugins.history')
        .config(historyConfig);

    function historyConfig(routerHelperProvider) {
        routerHelperProvider.configureStates(getStates());
    }

    function getStates() {
        return [
            {
                state: 'history',
                config: {
                    url: '/history',
                    component: 'history-view',
                    settings: {
                        weight: 3,
                        icon: 'history',
                        caption: 'History'
                    }
                }
            }
        ];
    }
}());