/* global angular */
(function () {
    'use strict';

    angular
        .module('blocks.error')
        .factory('errorService', errorService);

    function errorService($mdToast, $mdDialog) {
        var toast = $mdToast.simple()
            .textContent('Well, this is awkward...')
            .action('Details')
            .highlightAction(true)
            .position('bottom right')
            .hideDelay(5000);

        //TODO: Would be good if ngMaterial supports opening components by name: https://github.com/angular/material/issues/8409#issuecomment-220759188
        var dialog = {
            template: '<error-dialog error=\'vm.error\'></error-dialog>',
            bindToController: true,
            controllerAs: 'vm',
            controller: function () { }
        };

        return {
            showToast: showToast,
            showDialog: showDialog
        };

        function showToast(error) {
            $mdToast.show(toast).then(function (response) {
                if (response === 'ok') {
                    showDialog(error);
                }
            });
        }

        //TODO: Test
        function showDialog(error) {
            dialog.locals = {
                error: error
            };

            $mdDialog.show(dialog);
        }
    }
}());