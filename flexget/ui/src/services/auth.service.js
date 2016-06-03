(function () {
    'use strict';

    angular.module('flexget.services')
        .factory('authService', authService);

    function authService($state, $http, $q) {
        var isLoggedIn, prevState, prevParams;

        isLoggedIn = false;

        return {
            loggedIn: loggedIn,
			login: login,
			state: state
		};

		//TODO: Delegate success and failure to functions
		//TODO: test
		//TODO: Change state saving for new UI router system
		function loggedIn() {
			var def = $q.defer();

			if (isLoggedIn) {
				def.resolve(isLoggedIn);
			} else {
				$http.get("/api/server/version/")
					.then(function () {
						def.resolve();
					}, function (error) {
						def.reject()
					});
			}

			return def.promise;
		};

		function login(username, password, remember) {
			if (!remember) {
				remember = false;
			}

			return $http.post('/api/auth/login/', { username: username, password: password }, { params: { remember: remember } })
				.then(function () {
					loggedIn = true;

					if (prevState) {
						$state.go(prevState, prevParams);
					} else {
						$state.go('flexget.home');
					}
				});
		};

		function state(state, params) {
			if (state.name != 'login') {
				prevState = state;
				prevParams = params;
			}
		}
	};
})();