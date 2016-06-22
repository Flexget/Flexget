(function () {
	'use strict';
	angular
		.module("flexget.plugins.config")
		.component('configView', {
			templateUrl: 'plugins/config/config.tmpl.html',
			controllerAs: 'vm',
			controller: configController,
		});

	function configController($http, base64) {
		var vm = this;

		vm.aceOptions = {
			mode: 'yaml'
		};

		$http.get('/api/server/raw_config')
			.then(function (response) {
				var encoded = response.data.raw_config;
				vm.config = base64.decode(encoded);
			}, function (error) {
				// log error
				console.log(error);
			});

		vm.save = function () {
			console.log(vm.config);

		}
	}

})();