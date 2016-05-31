(function () {
	'use strict';

	angular.module('flexget.components')
		.run(authenticationSetup)
		.config(authenticationConfig);

		//TODO: Implement JWT, make back end first?
	function authenticationSetup($rootScope, $state, $http, toolBar, authService, $transitions) {

		$rootScope.$on('event:auth-loginRequired', function (event, timeout) {
			$state.go('login', { timeout: timeout });
		});


		var logout = function () {
			$http.get('/api/auth/logout/')
				.success(function () {
					$state.go('login');
				});
		};

		/* Ensure user is authenticated when changing states (pages) unless we are on the login page */
		$transitions.onBefore({ to: 'flexget.*' }, function () {
			authService.loggedIn()
				.catch(function () {
					// Not logged in
					//TODO: Work some more on this					
					//authService.state(toState, toParams);
					$rootScope.$broadcast('event:auth-loginRequired', false);
				});
		});

		toolBar.registerMenuItem('Manage', 'Logout', 'fa fa-sign-out', logout, 255);
	}

	function authenticationConfig($httpProvider, $stateProvider) {
		/* Register login page and redirect to page when login is required */
		$stateProvider.state('login', {
			url: '/login',
			controller: 'LoginController',
			controllerAs: 'vm',
			templateUrl: 'components/authentication/login.tmpl.html',
		});

		/* Intercept 401/403 http return codes and redirect to login page */

		$httpProvider
			.interceptors.push(['$rootScope', '$q', '$injector', function ($rootScope, $q, $injector) {
				var loginRequired = function () {
					var stateService = $injector.get('$state');
					var authService = $injector.get('authService');
					authService.state(stateService.current, stateService.params);
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
	}
})();