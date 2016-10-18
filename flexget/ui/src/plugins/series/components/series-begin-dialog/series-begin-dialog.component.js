/* global angular */
(function () {

    angular
        .module('plugins.series')
        .component('seriesBeginDialog', {
            templateUrl: 'plugins/series/components/series-begin-dialog/series-begin-dialog.tmpl.html',
            controller: seriesBeginDialogController,
            controllerAs: 'vm',
            bindings: {
                show: '<'
            }
        });

    function seriesBeginDialogController($mdDialog, seriesService) {
        var vm = this;

        vm.cancel = cancel;
        vm.$onInit = activate;
        vm.saveBegin = saveBegin;

        function activate() {
            vm.begin = vm.show['begin_episode'] ? vm.show['begin_episode'].identifier : undefined;
            vm.originalBegin = angular.copy(vm.begin);
        }

        function cancel() {
            $mdDialog.cancel();
        }

        function saveBegin() {
            var params = {
                'begin_episode': vm.begin
            };

            seriesService.updateShow(vm.show, params).then(function () {
                $mdDialog.hide(vm.begin);
            });
        }
    }
}());