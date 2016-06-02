(function () {
    'use strict';

    angular
        .module("flexget.components.home", [])
        .run(appRun);

    function appRun(routerHelper) {
        routerHelper.configureStates(getStates());
	};

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
					'/'
				]
            }
        ]
    }
})();