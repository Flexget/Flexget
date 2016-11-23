/* global angular */
(function () {
    'use strict';

    angular
        .module('plugins.pending')
        .component('pendingView', {
            templateUrl: 'plugins/pending/pending.tmpl.html',
            controllerAs: 'vm',
            controller: pendingController
        });

    function pendingController($filter, pendingService) {
        var vm = this;

        vm.$onInit = activate;
        vm.updateEntry = updateEntry;
            
        function activate() {
            getPending();
        }

        function getPending() {
            pendingService.getPending()
                .then(setEntries)
                .cached(setEntries);
        }

        function updateEntry(id, operation) {
            pendingService.updatePendingEntry(id, operation)
                .then(function (response) {
                    console.log(response);
                });
        }
        
        function setEntries(response) {
            vm.entries = response.data;
        }
    }
}());