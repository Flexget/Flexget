(function () {
    'use strict';

    angular
		.module("plugins.series")
		.run(appRun);

	function appRun(routerHelper) {
		routerHelper.configureStates(getStates());
	};

	function getStates() {
		return [
			{
				state: 'series',
				config: {
					url: '/series',
					component: 'seriesView',
					settings: {
						weight: 4,
						icon: 'tv',
						caption: 'Series'
					}
				}
			}
		]
	}
})();