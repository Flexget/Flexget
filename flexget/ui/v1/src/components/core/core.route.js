/* global angular */
(function () {
    'use strict';

    angular
        .module('components.core')
        .config(coreConfig);

    function coreConfig(routerHelperProvider) {
        routerHelperProvider.configureStates(getStates());
    }

    function getStates() {
        return [
            {
                state: 'flexget',
                config: {
                    abstract: true,
                    templateUrl: 'layout.tmpl.html'
                }
            }
        ];
    }
}());