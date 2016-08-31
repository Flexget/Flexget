/* global angular */
(function () {
    'use strict';

    angular
        .module('components.404')
        .config(notfoundConfig);

    function notfoundConfig(routerHelperProvider) {
        routerHelperProvider.configureStates(getStates(), '/404');
    }

    function getStates() {
        return [
            {
                state: '404',
                config: {
                    url: '/404',
                    component: 'notFound',
                    root: true
                }
            }
        ];
    }
}());