(function () {
    'use strict';

    angular
		.module("plugins.config")
		.run(appRun);

	function appRun(routerHelper) {
		routerHelper.configureStates(getStates());
	};

	function getStates() {
		return [
			{
				state: 'config',
				config: {
					url: '/config',
					component: 'configView',
					settings: {
						weight: 3,
						icon: 'pencil',
						caption: 'Config'
					}
				}
			}
		]
	}
})();