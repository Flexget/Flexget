(function () {
    'use strict';

    angular
        .module("flexget.components.home", ['angular.filter'])
        .run(appRun);

    function appRun(routerHelper) {
        routerHelper.configureStates(getStates());
    };

    function getStates() {
        return [
            {
                state: 'home',
                config: {
                    url: '/',
                    component: 'home'
                }
            }
        ]
    }
})();