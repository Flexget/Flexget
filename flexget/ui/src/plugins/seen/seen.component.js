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
        vm.getSeen = getSeen;
        
        var options = {};

        function activate() {
            getSeen(1);
        }

        function getSeen(page) {
            options.page = page;
            seenService.getSeen(options)
                .then(setEntries)
                .cached(setEntries)
                .finally(function (data) {
                    vm.currentPage = options.page;
                });
            
            function setEntries(response) {
                vm.entries = response.data;
                vm.linkHeader = response.headers().link;
            };
        }

        function deleteEntry(entry) {
            seenService.deleteEntryById(entry.id).then(function () {
                getSeen(options.page);
            });
        }
    }
}());