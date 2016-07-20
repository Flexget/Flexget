/* global angular */
(function () {
    'use strict';

    angular
		.module('plugins.server')
		.run(appRun);

	function appRun(serverService, toolBarService) {
		var reloadButton = {
			menu: 'Manage',
			type: 'menuItem',
			label: 'Reload',
			icon: 'refresh',
			action: serverService.reload,
			order: 127
		};

		var shutdownButton = {
			menu: 'Manage',
			type: 'menuItem',
			label: 'Shutdown',
			icon: 'power-off',
			action: serverService.shutdown,
			order: 128
        };

		toolBarService.registerItem(reloadButton);
		toolBarService.registerItem(shutdownButton);
	}
}());