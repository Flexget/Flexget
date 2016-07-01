(function () {
    'use strict';

    angular
		.module('components.auth')
        .factory('authService', authService);

    function authService($state, $http, $q) {
        var isLoggedIn, prevState, prevParams;

        isLoggedIn = false;

        return {
            loggedIn: loggedIn,
			login: login,
			logout: logout,
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
			
			function loginComplete(response) {
				isLoggedIn = true;
				if(prevState) {
					$state.go(prevState, prevParams);
				} else {
					$state.go('flexget.home');
				}
				return;
			};

			function loginCallFailed(error) {
				return $q.reject(error.data);
			};
		};

		function logout() {
			return $http.get('/api/auth/logout/')
				.then(logoutComplete)
				.catch(callFailed);

			function logoutComplete(response) {
				isLoggedIn = false;
				$state.go('login');
				return;
			};
		};
		
		function state(state, params) {
			if (state.name != 'login') {
				prevState = state;
				prevParams = params;
			}
		};

		function callFailed(error) {
			console.log(error);
			return exception.catcher(error);
        }
	};
})();