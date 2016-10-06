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
                links: '<',
                currentPage: '<'
            }
        });
    
    function paginationController() {
        var vm = this;

        vm.linkGroupFirst = function () {
            var rightDebt = Math.max(0,
                +vm.currentPage - (+vm.links.last.page - 2));
            return Math.max(1, +vm.currentPage - rightDebt - 2);
        };
        
        vm.linkGroupLast = function () {
            var leftDebt = Math.max(0,
                1 + 2 - (+vm.currentPage));
            return Math.min(+vm.links.last.page, +vm.currentPage + leftDebt + 2);
        };

        vm.setPage = function (page) {
            if (page !== vm.currentPage) {
                vm.loadData({ page: page });
            }     
        }
    }
})();