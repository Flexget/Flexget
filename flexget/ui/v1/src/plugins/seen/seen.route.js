/* global angular */
(function () {
    'use strict';

    angular
        .module('plugins.seen')
        .config(seenConfig);

    function seenConfig(routerHelperProvider) {
        routerHelperProvider.configureStates(getStates());
    }

    function getStates() {
        return [
            {
                state: 'seen',
                config: {
                    url: '/seen',
                    component: 'seen-view',
                    settings: {
                        weight: 7,
                        icon: 'eye',
                        caption: 'Seen'
                    }
                }
            }
        ];
    }
}());