/* global angular */
(function () {
    'use strict';

    angular
        .module('plugins.history')
        .component('historyView', {
            templateUrl: 'plugins/history/history.tmpl.html',
            controllerAs: 'vm',
            controller: historyController
        });

    function historyController(historyService) {
        var vm = this;

        vm.$onInit = activate;
        vm.search = search;
        vm.getHistory = getHistory;

        var options = {};

        function activate() {
            getHistory(1);
        }

        function search(taskName) {
            options.task = taskName || undefined;

            getHistory(1);
        }

        function getHistory(page) {
            options.page = page;
            historyService.getHistory(options)
                .then(setEntries)
                .cached(setEntries)
                .finally(function (data) {
                    vm.currentPage = options.page;
                });
        }
        
        function setEntries(response, itemCache) {
            vm.entries = response.data;
            vm.linkHeader = response.headers().link;
        }
    }
}());