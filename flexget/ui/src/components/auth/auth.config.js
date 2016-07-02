(function () {
	'use strict';

	angular
		.module('components.auth')
		.run(authenticationSetup)
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
					$rootScope.$broadcast('event:auth-loginRequired', true);
				});
		});
	}

	function authenticationConfig($httpProvider, $stateProvider) {

		/* Intercept 401/403 http return codes and redirect to login page */
		$httpProvider
			.interceptors.push(['$rootScope', '$state', '$q', '$injector', function ($rootScope,  $state, $q, $injector) {
				var loginRequired = function () {
					var authService = $injector.get('authService');
					authService.state($state.current, $state.params);
					$rootScope.$broadcast('event:auth-loginRequired', true);
				};

				return {
					responseError: function (rejection) {
						if (!rejection.config.ignoreAuthModule) {
							switch (rejection.status) {
								case 401:
								case 403:
									loginRequired();
									break;
							}
						}

						// otherwise, default behaviour
						return $q.reject(rejection);
					},
				};
			}]);
	};
})();