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

    function historyController($filter, historyService) {
        var vm = this;

        vm.$onInit = activate;
        vm.getHistory = getHistory;
        vm.changeOrder = changeOrder;

        vm.sortOptions = [
            "Task",
            "Filename",
            "Url",
            "Title",
            "Time",
            "Details"
        ];

        vm.sortOption = "Time";
        vm.searchTerm = "";
        vm.order = "desc";

        function activate() {
            getHistory();
        }

        function changeOrder() {
            vm.order === 'desc' ? setOrder('asc') : setOrder('desc');

            function setOrder(direction) {
                vm.order = direction;
                getHistory();
            }
        }

        function getHistory(page) {
            var options = {
                page: page || 1,
                task: vm.searchTerm || undefined,
                sort_by: $filter('lowercase')(vm.sortOption),
                order: vm.order
            }
            historyService.getHistory(options)
                .then(setEntries)
                .cached(setEntries)
                .finally(function (data) {
                    vm.currentPage = options.page;
                });
        }
        
        function setEntries(response) {
            vm.entries = response.data;
            vm.linkHeader = response.headers().link;
        }
    }
}());