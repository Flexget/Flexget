(function () {
	'use strict';

	angular
		.module('flexget.plugins.seen')
		.component('seenView', {
			templateUrl: 'plugins/seen/seen.tmpl.html',
			controllerAs: 'vm',
			controller: seenController,
		});

	function seenController($http) {
		var vm = this;

		vm.title = 'Seen';

		$http.get('/api/seen/', { params: { max: 20 } })
			.success(function handleSeen(data) {
				vm.entries = data.seen_entries;
			})
			.error(function handlerSeenError(data) {
				// log error
			});
	}
});