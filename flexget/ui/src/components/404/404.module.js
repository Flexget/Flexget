(function () {
    'use strict';

    angular
        .module("flexget.components.404", [])
        .run(appRun);

    function appRun(routerHelper) {
        routerHelper.configureStates(getStates(), '/404');
		
		console.log(routerHelper.getStates());
    };

    function getStates() {
        return [
            {
                state: '404',
                config: {
                    url: '/404',
                    component: 'notFound'
                }
            }
        ]
    }
})();