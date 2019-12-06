/* global angular */
(function () {
    'use strict';

    angular
        .module('plugins.schedule')
        .config(scheduleConfig);

    function scheduleConfig(routerHelperProvider) {
        routerHelperProvider.configureStates(getStates());
    }

    function getStates() {
        return [
            {
                state: 'schedule',
                config: {
                    url: '/schedule',
                    component: 'schedule-view',
                    settings: {
                        weight: 6,
                        icon: 'calendar',
                        caption: 'Schedule'
                    }
                }
            }
        ];
    }
}());