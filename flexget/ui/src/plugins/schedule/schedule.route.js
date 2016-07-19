(function () {
    'use strict';

    angular
		.module("plugins.schedule")
		.run(appRun);

	function appRun(routerHelper) {
		routerHelper.configureStates(getStates());
	}

	function getStates() {
		return [
			{
				state: 'schedule',
				config: {
					url: '/schedule',
					component: 'schedule-view',
					settings: {
						weight: 6,
						icon: 'calendar',
						caption: 'Schedule'
					}
				}
			}
		]
	}
}());