(function () {
    'use strict';

    angular.module('flexget.components')
        .factory('errorService', errorService);

    function errorService($mdToast, $mdDialog) {
        var toast = {
            templateUrl: 'components/error/toast.tmpl.html',
            position: 'bottom right',
            controller: toastController,
            controllerAs: 'vm'
        }

        var dialog = {
            templateUrl: 'components/error/dialog.tmpl.html',
            controller: dialogController,
            controllerAs: 'vm'
        }

        return {
            showToast: function() {           
                $mdToast.show(toast);
            }
        }

        
        function dialogController() {
            var vm = this;

            vm.close = function() {
                $mdDialog.hide();
            }
        }

        function toastController() {
            var vm = this;

            vm.text = "Damnit Flexget, you had one job!";

            vm.openDetails = function() {
                $mdDialog.show(dialog);
            }
        };
    }

})();