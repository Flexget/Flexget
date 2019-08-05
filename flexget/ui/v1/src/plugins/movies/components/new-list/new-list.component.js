/* global angular */
(function () {
    'use strict';

    angular
        .module('plugins.movies')
        .component('newList', {
            templateUrl: 'plugins/movies/components/new-list/new-list.tmpl.html',
            controller: newListController,
            controllerAs: 'vm',
            bindings: {
                lists: '<'
            }
        });

    function newListController($mdDialog, moviesService) {
        var vm = this;

        vm.cancel = cancel;
        vm.saveList = saveList;

        function cancel() {
            $mdDialog.cancel();
        }

        function saveList() {
            moviesService.createList(vm.listName).then(function (newList) {
                $mdDialog.hide(newList);
            });
        }
    }
}());