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

        function activate() {
            getHistory();
        }

        function search() {
            historyService.getHistoryForTask({ task: vm.taskName })
                .then(setEntries)
                .cached(setEntries);
        }

        function getHistory() {
            historyService.getHistory()
                .then(setEntries)
                .cached(setEntries);
        }

         function setEntries(data) {
            vm.entries = data;
        }
    }
}());