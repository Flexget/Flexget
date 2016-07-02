(function () {
    'use strict';

    angular
        .module("components.auth")
		.run(appRun);

    function appRun(routerHelper, toolBarService, authService) {
        routerHelper.configureStates(getStates());

		var logoutItem = {
			menu: 'Manage',
			type: 'menuItem',
			label: 'Logout',
			icon: 'sign-out',
			action: logout,
			order: 256
		}

		function logout() {
			authService.logout();
		}

		toolBarService.registerItem(logoutItem);
    };

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
        ]
    }
})();