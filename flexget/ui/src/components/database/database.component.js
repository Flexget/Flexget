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

    function databaseController($mdDialog, $sce, $mdToast, databaseService) {
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
            databaseService.cleanup()
                .then(openSuccess);
        }

        function vacuum() {
            databaseService.vacuum()
                .then(openSuccess);
        }

        function openSuccess(data) {
            var toast = $mdToast.simple()
                .textContent(data.message)
                .position('bottom right')
                .capsule(true)
                .toastClass('success');

            $mdToast.show(toast);
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
            var confirm = $mdDialog.confirm()
                .title('Confirm resetting plugin.')
                .htmlContent($sce.trustAsHtml('Are you sure you want to reset the database for <b>' + vm.selectedPlugin + '</b>?'))
                .ok('Reset')
                .cancel('No');

            $mdDialog.show(confirm).then(function () {
                var params = vm.selectedPlugin;
                databaseService.resetPlugin(params)
                    .then(openSuccess);
            });
        }
    }
}());
