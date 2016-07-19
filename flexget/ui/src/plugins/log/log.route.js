(function () {
    'use strict';

    angular
		.module("plugins.log")
		.run(appRun);

	function appRun(routerHelper, toolBarService, $state) {
		routerHelper.configureStates(getStates());

		var logButton = {
			type: 'button',
			label: 'Log',
			icon: 'file-text-o',
			action: goToRoute,
			order: 1
		}

		function goToRoute() {
			$state.go('flexget.log');
		}

		toolBarService.registerItem(logButton);
	}

	function getStates() {
		return [
			{
				state: 'log',
				config: {
					url: '/log',
					component: 'log-view',
					settings: {
						weight: 1,
						icon: 'file-text-o',
						caption: 'Log'
					}
				}
			}
		]
	}

	
}());