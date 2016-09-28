/* global angular */
(function () {
    'use strict';

    angular
        .module('plugins.seen')
        .component('seenView', {
            templateUrl: 'plugins/seen/seen.tmpl.html',
            controllerAs: 'vm',
            controller: seenController
        });

    function seenController(seenService) {
        var vm = this;

        vm.$onInit = activate;
        vm.deleteEntry = deleteEntry;

        function activate() {
            getSeen();
        }

        function getSeen() {
            seenService.getSeen()
                .then(setEntries)
                .cached(setEntries);
            
            function setEntries(data) {
                vm.entries = data;
            };
        }

        function deleteEntry(entry) {
            seenService.deleteEntryById(entry.id).then(function () {
                getSeen();
            });
        }
    }
}());