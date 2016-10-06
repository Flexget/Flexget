/* global angular */
(function () {
    'use strict';
    
    angular
        .module('components.pagination')
        .component('fgPagination', {
            templateUrl: 'components/pagination/pagination.tmpl.html',
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

        vm.$onChanges = function (changes) {
            console.log(changes);
        }

        vm.setPage = function (page) {
            vm.loadData({ page: page });
        }
    }
})();