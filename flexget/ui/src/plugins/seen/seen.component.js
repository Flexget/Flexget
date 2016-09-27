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

    function seenController($mdDialog, $sce, seenService) {
        var vm = this;

        vm.$onInit = activate;
        vm.deleteEntry = deleteEntry;

        function activate() {
            getSeen();
        }

        function getSeen() {
            return seenService.getSeen().then(function (data) {
                vm.entries = data.seen_entries;
            });
        }

        function deleteEntry(entry) {
            var confirm = $mdDialog.confirm()
                .title('Confirm forgetting Seen Entry.')
                .htmlContent($sce.trustAsHtml('Are you sure you want to delete <b>' + entry.title + '</b>?'))
                .ok('Forget')
                .cancel('No');

            $mdDialog.show(confirm).then(function () {
                seenService.deleteEntryById(entry.id).then(function () {
                    getSeen();
                });
            });
        }
    }
}());