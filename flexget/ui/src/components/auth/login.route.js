/* global angular */
(function () {
    'use strict';

    angular
        .module('components.auth')
        .config(authConfig);

    function authConfig(/*authService,*/ routerHelperProvider/*, toolBarService*/) {
        routerHelperProvider.configureStates(getStates());

        /*var logoutItem = {
            menu: 'Manage',
            type: 'menuItem',
            label: 'Logout',
            icon: 'sign-out',
            action: authService.logout,
            order: 255
        };

        toolBarService.registerItem(logoutItem);*/
    }

    function getStates() {
        return [
            {
                state: 'login',
                config: {
                    url: '/login',
                    component: 'login',
                    root: true,
                    params: {
                        timeout: false
                    }
                }
            }
        ];
    }
}());