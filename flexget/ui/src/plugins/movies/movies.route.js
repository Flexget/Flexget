(function () {
    'use strict';

    angular
		.module("plugins.movies")
		.run(appRun);

	function appRun(routerHelper) {
		routerHelper.configureStates(getStates());
	};

	function getStates() {
		return [
			{
				state: 'movies',
				config: {
					url: '/movies',
					component: 'moviesView',
					settings: {
						weight: 5,
						icon: 'film',
						caption: 'Movies'
					}
				}
			}
		]
	}
})();