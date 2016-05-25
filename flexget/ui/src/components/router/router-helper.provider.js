(function () {
	'use strict';

	angular
		.module('flexget.components.router')
		.provider('routerHelper', routerHelperProvider);

	function routerHelperProvider($locationProvider, $stateProvider, $urlRouterProvider) {
		if (!(window.history && window.history.pushState)) {
			window.location.hash = '/';
		}

		$locationProvider.html5Mode(true);
		
		

		this.$get = RouterHelper;

		function RouterHelper($location, $rootScope, $state) {
			var handlingStateChangeError = false;
			var hasOtherwise = false;
			var service = {
				configureStates: configureStates,
				getStates: getStates
			};

			init();

			return service;

			function configureStates(states, otherwisePath) {
				states.forEach(function (state) {
					$stateProvider.state((state.config.abstract ? '' : 'flexget.') + state.state, state.config);
				});
				if (otherwisePath && !hasOtherwise) {
					hasOtherwise = true;
					$urlRouterProvider.otherwise(otherwisePath);
				}
			}

			function handleRoutingErrors() {
				$rootScope.$on('$stateChangeError', function (event, toState, toParams, fromState, fromParams, error) {
					if (handlingStateChangeError) {
						return;
					}

					var destination = (toState &&
						(toState.title || toState.name || toState.loadedTemplateUrl)) ||
						'unknown target';

					var msg = 'Error routing to ' + destination + '. ' +
						(error.data || '') + '. <br/>' + (error.statusText || '') +
						': ' + (error.status || '');

					console.log(msg);


					handlingStateChangeError = true;
					$location.path('/');

					//TODO: Maybe add some logging here to indicate the routing failed
				});
			}


			function init() {
				handleRoutingErrors();
			};

			function getStates() { return $state.get(); }
		};
	};
})();