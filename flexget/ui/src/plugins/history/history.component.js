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
            return historyService.getHistoryForTask({ task: vm.taskName }).then(function (data) {
                vm.entries = data.entries;
            });
        }

        function getHistory() {
            return historyService.getHistory().then(function (data) {
                vm.entries = data.entries;
            });
        }
    }
}());