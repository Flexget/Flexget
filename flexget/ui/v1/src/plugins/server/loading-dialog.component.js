/* global angular */
(function () {
    'use strict';

    angular
        .module('plugins.server')
        .component('loadingDialog', {
            templateUrl: 'plugins/server/loading-dialog.tmpl.html',
            controller: loadingDialogController,
            controllerAs: 'vm',
            bindings: {
                title: '<',
                action: '<'
            }
        });

    function loadingDialogController($mdDialog) {
        var vm = this;

        vm.$onInit = activate;
        vm.close = close;

        function activate() {
            vm.loading = true;

            vm.action().then(function (data) {
                setValues(data);
            }, function (error) {
                setValues(error);
            }).finally(function () {
                vm.loading = false;
            });
        }

        function setValues(obj) {
            vm.title = obj.title;
            vm.content = obj.message;
        }

        function close() {
            $mdDialog.hide();
        }
    }
}());