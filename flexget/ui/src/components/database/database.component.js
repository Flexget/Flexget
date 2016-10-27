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
    }
}());