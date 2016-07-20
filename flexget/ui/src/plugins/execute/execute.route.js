(function () {
    'use strict';

    angular
		.module('plugins.execute')
		.run(appRun);

	function appRun(routerHelper) {
		routerHelper.configureStates(getStates());
	}

	function getStates() {
		return [
			{
				state: 'execute',
				config: {
					url: '/execute',
					component: 'execute-view',
					settings: {
						weight: 2,
						icon: 'cog',
						caption: 'Execute'
					}
				}
			}
		];
	}
}());