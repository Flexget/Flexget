/* global angular, ace */
(function () {
    'use strict';

    angular
        .module('plugins.config')
        .component('configView', {
            templateUrl: 'plugins/config/config.tmpl.html',
            controllerAs: 'vm',
            controller: configController
        });

    function configController($http, base64, $mdDialog, CacheFactory, configService) {
        var vm = this;

        vm.$onInit = activate;
        vm.updateTheme = updateTheme;
        vm.saveConfiguration = saveConfiguration;
        vm.changeContent = changeContent;
        vm.variables = false;

        var aceThemeCache, editor;

        function activate() {
            loadConfig();
            initCache();

            setupAceOptions();
        }

        function changeContent() {
            vm.variables ? loadConfig() : loadVariables();
            vm.variables = !vm.variables;
        }

        function initCache() {
            if (!CacheFactory.get('aceThemeCache')) {
                CacheFactory.createCache('aceThemeCache', {
                    storageMode: 'localStorage'
                });
            }

            aceThemeCache = CacheFactory.get('aceThemeCache');
        }

        function loadConfig() {
            configService.getRawConfig()
                .then(decode)
                .cached(decode);
            
            function decode(response) {
                var decoded = base64.decode(response.data.raw_config);
                setConfiguration(decoded);
            }
        }

        function loadVariables() {
            configService.getVariables()
                .then(setVariables)
                .cached(setVariables);
            
            function setVariables(response) {
                var converted = YAML.stringify(response.data);
                setConfiguration(converted);
            }
        }

        function setConfiguration(config) {
            vm.configuration = config;
            editor.focus();
            saveOriginalValues();
        }

        function saveOriginalValues() {
            vm.originalValues = angular.copy(vm.configuration);
        }

        function setupAceOptions() {
            vm.aceOptions = {
                mode: 'yaml',
                theme: getTheme(),
                onLoad: aceLoaded
            };

            var themelist = ace.require('ace/ext/themelist');
            vm.themes = themelist.themes;
        }

        function aceLoaded(_editor) {
            editor = _editor;
            //Get all commands, but keep the find command
            var commandsToRemove = [
                'transposeletters',
                'gotoline'
            ];

            _editor.commands.removeCommands(commandsToRemove);

            _editor.commands.addCommand({
                name: 'saveConfiguration',
                bindKey: { win: 'Ctrl-S', mac: 'Command-S' },
                exec: function () {
                    if (vm.configuration !== vm.originalValues) {
                        saveConfiguration();
                    }
                }
            });

            _editor.setShowPrintMargin(false);
        }

        function getTheme() {
            var theme = aceThemeCache.get('theme');
            return theme ? theme : 'chrome';
        }

        function updateTheme() {
            aceThemeCache.put('theme', vm.aceOptions.theme);
        }

        function saveConfiguration() {
            vm.variables ? saveVariables() : saveConfig();
        }

        function saveVariables() {
            var converted = YAML.parse(vm.configuration);
            configService.saveVariables(converted)
                .then(function () {
                    updateSuccess();
                }, function (error) {
                    console.log(error);
                    // TODO: Check errors
                    delete vm.errors;
                    delete vm.yamlError;
                    vm.errors = error;
                });
        }

        function saveConfig() {
            var encoded = base64.encode(vm.configuration);
            configService.saveRawConfig(encoded)
                .then(function () {
                    updateSuccess();
                }, function (error) {
                    delete vm.errors;
                    delete vm.yamlError;
                    error.errors ? vm.errors = error.errors : vm.yamlError = error;
                });
        }

        function updateSuccess() {
            var dialog = $mdDialog.alert()
                .title('Update success')
                .ok('Ok')
                .textContent('Your ' + (vm.variables ? 'variables have' : 'config has') + ' been successfully updated');
                    
            $mdDialog.show(dialog).then(function () {
                editor.focus();
            });

            delete vm.errorMessage;
            delete vm.errors;
            delete vm.yamlError;
                    
            saveOriginalValues();
        }
    }
}());
