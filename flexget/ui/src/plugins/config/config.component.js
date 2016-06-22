(function () {
	'use strict';
	angular
		.module("flexget.plugins.config")
		.component('configView', {
			templateUrl: 'plugins/config/config.tmpl.html',
			controllerAs: 'vm',
			controller: configController,
		});

	function configController($http, base64, $mdDialog) {
		var vm = this;
		
		vm.aceOptions = {
			mode: 'yaml',
			theme: 'chrome'
		};

		var themelist = ace.require('ace/ext/themelist');
		vm.themes = themelist.themes;

		$http.get('/api/server/raw_config')
			.then(function (response) {
				var encoded = response.data.raw_config;
				vm.config = base64.decode(encoded);
				vm.origConfig = angular.copy(vm.config);
			}, function (error) {
				// log error
				console.log(error);
			});

		vm.save = function () {
			var encoded = base64.encode(vm.config);
			$http.post('/api/server/raw_config', { raw_config: encoded })
				.then(function (data) {
					var dialog = $mdDialog.alert()
						.title("Update success")
						.ok("Ok")
						.textContent("Your config file has been successfully updated")

					$mdDialog.show(dialog);
				}, function (error) {
					vm.errors = error.data.errors;
				});
		}
	};

})();