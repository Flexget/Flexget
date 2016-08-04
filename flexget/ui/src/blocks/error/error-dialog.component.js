/* global angular*/
(function () {
    'use strict';

    angular
        .module('blocks.error')
        .component('errorDialog', {
            templateUrl: 'blocks/error/error-dialog.tmpl.html',
            controller: errorDialogController,
            controllerAs: 'vm',
            bindings: {
                error: '<'
            }
        });

    function errorDialogController($mdDialog) {
        var vm = this;

        vm.close = close;

        function close() {
            $mdDialog.hide();
        }
    }
}());