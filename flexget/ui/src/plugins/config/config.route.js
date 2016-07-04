(function () {
    'use strict';

    angular
		.module("plugins.config")
		.run(appRun);

	function appRun(routerHelper, toolBarService, $state) {
		routerHelper.configureStates(getStates());

		var configButton = {
			type: 'button',
			label: 'Config',
			icon: 'pencil',
			action: goToRoute,
			order: 1
		}

		function goToRoute() {
			$state.go('flexget.config');
		};

		toolBarService.registerItem(configButton);
	};

	function getStates() {
		return [
			{
				state: 'config',
				config: {
					url: '/config',
					component: 'config-view',
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