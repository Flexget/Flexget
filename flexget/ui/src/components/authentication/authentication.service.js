(function () {
    'use strict';

    angular.module('flexget.components')
        .factory('authService', authService);

    function authService($state, $http, $q) {
        var loggedIn, prevState, prevParams;

        loggedIn = false;

        return {
            loggedIn: function () {
                var def = $q.defer();

                if (loggedIn) {
                    def.resolve(loggedIn);
                } else {
                    $http.get("/api/server/version/")
                        .success(function () {
                            def.resolve();
                        })
                        .error(function (data) {
                            def.reject()
                        })
                }

                return def.promise;
            },
            login: function (username, password, remember) {
                if (!remember) {
                    remember = false;
                }

                return $http.post('/api/auth/login/?remember=' + remember, {username: username, password: password})
                    .success(function () {
                        loggedIn = true;

                        if (prevState) {
                            $state.go(prevState, prevParams);
                        } else {
                            $state.go('home');
                        }

                    })
            },
            state: function (state, params) {
                prevState = state;
                prevParams = params;
            }
        }
    }

})();