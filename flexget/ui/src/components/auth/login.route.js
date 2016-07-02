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
			action: authService.logout,
			order: 256
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