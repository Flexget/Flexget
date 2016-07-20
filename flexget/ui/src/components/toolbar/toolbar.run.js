/* global angular */
(function () {
	'use strict';

	angular
		.module('components.toolbar')
		.run(toolbarSetup);

	function toolbarSetup(toolBarService) {
		var manageMenu = {
			type: 'menu',
			label: 'Manage',
			icon: 'cog',
			items: [],
			order: 255
		};

		//Register default Manage menu
		toolBarService.registerItem(manageMenu);
	}
}());