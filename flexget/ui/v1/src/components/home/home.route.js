/* global angular */
(function () {
    'use strict';

    angular
        .module('components.home')
        .config(homeConfig);

    function homeConfig(routerHelperProvider) {
        routerHelperProvider.configureStates(getStates());
    }

    function getStates() {
        return [
            {
                state: 'home',
                config: {
                    url: '/',
                    component: 'home'
                },
                when: [
                    '',
                    '/',
                    '/home'
                ]
            }
        ];
    }
}());