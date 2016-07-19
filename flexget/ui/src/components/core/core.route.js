(function () {
    'use strict';

    angular
        .module("components.core")
        .run(appRun);

    function appRun(routerHelper) {
        routerHelper.configureStates(getStates());
	}

    function getStates() {
        return [
            {
				state: 'flexget',
				config: {
					abstract: true,
					templateUrl: 'layout.tmpl.html'
				}
			}
        ]
    }
}());