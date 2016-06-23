(function () {
    'use strict';

    angular
		.module("plugins.history")
		.run(appRun);

	function appRun(routerHelper) {
		routerHelper.configureStates(getStates());
	};

	function getStates() {
		return [
			{
				state: 'history',
				config: {
					url: '/history',
					component: 'historyView',
					settings: {
						weight: 3,
						icon: 'history',
						caption: 'History'
					}
				}
			}
		]
	}
})();