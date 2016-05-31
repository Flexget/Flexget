(function () {
    'use strict';

    angular.module('blocks.error')
        .factory('errorService', errorService);

    function errorService($mdToast, $mdDialog) {
        return {
            showToast: function(error) {
                 var toast = {
                    templateUrl: 'components/error/toast.tmpl.html',
                    position: 'bottom right',
                    controller: toastController,
                    controllerAs: 'vm',
                    locals: {
                        error: error
                    }
                }

                $mdToast.show(toast);
            }
        }

        function dialogController(error) {
            var vm = this;

            vm.error = error;

            vm.close = function() {
                $mdDialog.hide();
            }
        }

        function toastController(error) {
            var vm = this;

            var dialog = {
                templateUrl: 'components/error/dialog.tmpl.html',
                controller: dialogController,
                controllerAs: 'vm',
                locals: {
                    error: error
                }
            }

            vm.text = "Damnit Flexget, you had one job!";

            vm.openDetails = function() {
                $mdDialog.show(dialog);
            }
        };
    }

})();