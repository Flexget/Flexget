/* global angular*/
(function () {
    'use strict';

    angular
        .module('components.auth')
        .run(authenticationSetup)
        .factory('authInterceptor', authInterceptor)
        .config(authenticationConfig);

    function authenticationSetup($rootScope, $state, $transitions, authService) {
        $rootScope.$on('event:auth-loginRequired', function (event, timeout) {
            $state.go('login', { timeout: timeout });
        });

        /* Ensure user is authenticated when changing states (pages) unless we are on the login page */
        $transitions.onBefore({ to: 'flexget.*' }, function ($transition$) {
            authService.loggedIn()
                .catch(function () {
                    authService.state($transition$.to(), $transition$.params());
                    $rootScope.$broadcast('event:auth-loginRequired', false);
                });
        });
    }

    function authenticationConfig($httpProvider) {
        $httpProvider.interceptors.push('authInterceptor');
    }

    function authInterceptor($injector, $q, $rootScope, $state) {
        /* Intercept 401/403 http return codes and redirect to login page */
        return {
            responseError: responseError
        };

        function loginRequired() {
            var authService = $injector.get('authService');
            authService.state($state.current, $state.params);
            $rootScope.$broadcast('event:auth-loginRequired', true);
        }

        function responseError(rejection) {
            if (!rejection.config.ignoreAuthModule) {
                switch (rejection.status) {
                    case 401:
                    case 403:
                        loginRequired();
                        break;
                }
            }
            return $q.reject(rejection);
        }
    }
}());