(function () {
    'use strict';

    angular
		.module("plugins.log")
		.run(appRun);

	function appRun(routerHelper) {
		routerHelper.configureStates(getStates());
	};

	function getStates() {
		return [
			{
				state: 'log',
				config: {
					url: '/log',
					component: 'logView',
					settings: {
						weight: 1,
						icon: 'file-text-o',
						caption: 'Log'
					}
				}
			}
		]
	}
})();