(function () {
    'use strict';

    angular
		.module("plugins.seen")
		.run(appRun);

	function appRun(routerHelper) {
		routerHelper.configureStates(getStates());
	}

	function getStates() {
		return [
			{
				state: 'seen',
				config: {
					url: '/seen',
					component: 'seen-view',
					settings: {
						weight: 7,
						icon: 'eye',
						caption: 'Seen'
					}
				}
			}
		]
	}
})();