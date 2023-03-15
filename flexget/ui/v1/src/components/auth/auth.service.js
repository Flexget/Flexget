/* global angular */
(function () {
    'use strict';

    angular
        .module('components.auth')
        .factory('authService', authService);

    function authService($http, $q, $state, exception) {
        var isLoggedIn, prevState, prevParams;

        isLoggedIn = false;

        return {
            loggedIn: loggedIn,
            login: login,
            logout: logout,
            state: state
        };

        //TODO: Implement idling system, that resets the isLoggedIn variable from the authservice


        //TODO: Test this function
        function loggedIn() {
            var def = $q.defer();

            if (isLoggedIn) {
                def.resolve(isLoggedIn);
            } else {
                $http.get('/api/server/version/', {
                    ignoreAuthModule: true
                })
                    .then(function () {
                        isLoggedIn = true;
                        def.resolve();
                    }, function () {
                        def.reject();
                    });
            }

            return def.promise;
        }

        function login(credentials, remember) {
            if (!remember) {
                remember = false;
            }

            return $http.post('/api/auth/login/', credentials,
                {
                    params: { remember: remember },
                    ignoreAuthModule: true
                })
                .then(loginComplete)
                .catch(loginCallFailed);

            function loginComplete() {
                isLoggedIn = true;
                if(prevState) {
                    $state.go(prevState, prevParams);
                } else {
                    $state.go('flexget.home');
                }
                return;
            }

            function loginCallFailed(error) {
                return $q.reject(error.data);
            }
        }

        function logout() {
            return $http.post('/api/auth/logout/')
                .then(logoutComplete)
                .catch(callFailed);

            function logoutComplete() {
                isLoggedIn = false;
                prevState = null;
                prevParams = null;
                $state.go('login');
                return;
            }
        }

        function state(state, params) {
            if (state.name !== 'login') {
                prevState = state.name;
                prevParams = params;
            }
        }

        function callFailed(error) {
            return exception.catcher(error);
        }
    }
}());
