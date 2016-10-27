/* global angular */
(function () {
    'use strict';

    angular
        .module('components.database')
        .component('databaseSidebar', {
            templateUrl: 'components/database/database.tmpl.html',
            controllerAs: 'vm',
            controller: databaseController
        });

    function databaseController(databaseService) {
        var vm = this;

        vm.$onInit = activate;
        vm.cleanup = cleanup;
        vm.vacuum = vacuum;
        vm.searchPlugin = searchPlugin;
        vm.resetPlugin = resetPlugin;
        
        function activate() {
            databaseService.getPlugins()
                .then(setPlugins)
                .cached(setPlugins);
        }
        
        function setPlugins(response) {
            vm.plugins = response.data;
        }

        function cleanup() {
            databaseService.cleanup();
        }

        function vacuum() {
            databaseService.vacuum();
        }

        function searchPlugin(query) {
            var results = query ? vm.plugins.filter(createFilterFor(query)) : vm.plugins;
            return results;

            function createFilterFor(query) {
                var lowercaseQuery = angular.lowercase(query);

                return function filterFn(plugin) {
                    return angular.lowercase(plugin).indexOf(lowercaseQuery) != -1;
                }
            }
        }

        function resetPlugin() {
            var params = {
                plugin_name: vm.selectedPlugin
            }
            databaseService.resetPlugin(params)
                .then(function (response) {
                    console.log('yay, success!', response);
                });
        }
    }
}());