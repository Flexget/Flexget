(function () {
	'use strict';
	angular
		.module("plugins.config")
		.component('configView', {
			templateUrl: 'plugins/config/config.tmpl.html',
			controllerAs: 'vm',
			controller: configController,
		});

	function configController($http, base64, $mdDialog, CacheFactory, configService) {
		var vm = this;

		vm.$onInit = activate;
		vm.updateTheme = updateTheme;
		vm.saveConfig = saveConfig;

		var aceThemeCache;

		function activate() {
			loadConfig();
			initCache();

			setupAceOptions();
		};

		function initCache() {
			if (!CacheFactory.get('aceThemeCache')) {
				CacheFactory('aceThemeCache', {
					storageMode: 'localStorage'
				});
			}

			aceThemeCache = CacheFactory.get('aceThemeCache');
		}

		function loadConfig() {
			configService.getRawConfig().then(function (data) {
				var encoded = data.raw_config;
				vm.config = base64.decode(encoded);
				saveOriginalConfig();
			});
		}

		function saveOriginalConfig() {
			vm.origConfig = angular.copy(vm.config);
		}

		function setupAceOptions() {
			vm.aceOptions = {
				mode: 'yaml',
				theme: getTheme(),
				onLoad: aceLoaded
			}

			var themelist = ace.require('ace/ext/themelist');
			vm.themes = themelist.themes;
		}

		function aceLoaded(_editor) {
			_editor.setShowPrintMargin(false);
		}

		function getTheme() {
			var theme = aceThemeCache.get('theme');
			return theme ? theme : 'chrome';
		}

		function updateTheme() {
			aceThemeCache.put('theme', vm.aceOptions.theme);
		}

		function saveConfig() {
			var encoded = base64.encode(vm.config);
			$http.post('/api/server/raw_config', { raw_config: encoded })
				.then(function (data) {
					var dialog = $mdDialog.alert()
						.title("Update success")
						.ok("Ok")
						.textContent("Your config file has been successfully updated")

					$mdDialog.show(dialog);
					saveOriginalConfig();
				}, function (error) {
					vm.errors = error.data.errors;
				});
		}
	};
})();
