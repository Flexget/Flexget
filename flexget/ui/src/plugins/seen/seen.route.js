(function () {
    'use strict';

    angular
		.module("plugins.seen")
		.run(appRun);

	function appRun(routerHelper) {
		routerHelper.configureStates(getStates());
	};

	function getStates() {
		return [
			{
				state: 'seen',
				config: {
					url: '/seen',
					component: 'seenView',
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