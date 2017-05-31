/* global angular */
(function () {
    'use strict';
    
    angular
        .module('blocks.pagination')
        .component('fgPagination', {
            templateUrl: 'blocks/pagination/pagination.tmpl.html',
            controllerAs: 'vm',
            controller: paginationController,
            bindings: {
                loadData: '&',
                linkHeader: '<',
                currentPage: '<'
            }
        });
    
    function paginationController(linkHeaderParser) {
        var vm = this;

        vm.linkGroupFirst = linkGroupFirst;
        vm.linkGroupLast = linkGroupLast;
        vm.setPage = setPage;
        vm.$onChanges = handleChanges;
        
        function handleChanges(changesObj) {
            if (changesObj.linkHeader) {
                var links = changesObj.linkHeader.currentValue ? linkHeaderParser.parse(vm.linkHeader) : {};

                vm.prev = links.prev;
                vm.next = links.next;
                vm.last = links.last;
            }
        }

        function linkGroupFirst() {
            var rightDebt = vm.last ? Math.max(0,
                +vm.currentPage - (+vm.last.page - 2)) : 0;
            return Math.max(1, +vm.currentPage - rightDebt - 2);
        }
        
        function linkGroupLast() {
            var leftDebt = Math.max(0,
                1 + 2 - (+vm.currentPage));
            return Math.min(vm.last ? +vm.last.page : 0, +vm.currentPage + leftDebt + 2);
        }

        function setPage(page) {
            if (page !== vm.currentPage) {
                vm.loadData({ page: page });
            }
        }
    }
})();