(function () {
    'use strict';

    angular
        .module("components.login")
		.run(appRun);

    function appRun(routerHelper) {
        routerHelper.configureStates(getStates());
    };

    function getStates() {
        return [
            {
                state: 'login',
                config: {
                    url: '/login',
                    component: 'login',
					root: true
                }
            }
        ]
    }
})();