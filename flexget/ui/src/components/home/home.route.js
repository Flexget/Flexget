(function () {
    'use strict';

    angular
        .module("components.home")
        .run(appRun);

    function appRun(routerHelper) {
        routerHelper.configureStates(getStates());
	}

    function getStates() {
        return [
            {
                state: 'home',
                config: {
                    url: '/',
                    component: 'home'
                },
				when: [
					'',
					'/',
					'/home'
				]
            }
        ]
    }
}());