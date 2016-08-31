/* global angular */
(function () {
    'use strict';

    angular
        .module('plugins.series')
        .config(seriesConfig);

    function seriesConfig(routerHelperProvider) {
        routerHelperProvider.configureStates(getStates());
    }

    function getStates() {
        return [
            {
                state: 'series',
                config: {
                    url: '/series',
                    component: 'series-view',
                    settings: {
                        weight: 4,
                        icon: 'tv',
                        caption: 'Series'
                    }
                }
            }
        ];
    }
}());