/* global angular */
(function () {
    'use strict';

    angular
        .module('plugins.movies')
        .config(moviesConfig);

    function moviesConfig(routerHelperProvider) {
        routerHelperProvider.configureStates(getStates());
    }

    function getStates() {
        return [
            {
                state: 'movies',
                config: {
                    url: '/movies',
                    component: 'movies-view',
                    settings: {
                        weight: 5,
                        icon: 'film',
                        caption: 'Movies'
                    }
                }
            }
        ];
    }
}());