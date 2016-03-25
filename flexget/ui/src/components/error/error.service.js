(function () {
    'use strict';

    angular.module('flexget.components')
        .factory('errorService', errorService);

    function errorService($mdToast, $mdDialog) {
        return {
            showToast: function(vars) {
                var toast = {
                    templateUrl: 'components/error/toast.tmpl.html',
                    position: 'bottom right',
                    controller: function() {
                        var vm = this;

                        vm.text = "Damnit Flexget, you had one job!";
                        /*vm.test = vars.text;

                        vm.openMoreInfo = function(e) {
                            $mdDialog
                              .show($mdDialog
                                .alert()
                                .title('More info goes here.')
                                .textContent('Something witty.')
                                .ariaLabel('More info')
                                .ok('Got it')
                                .targetEvent(e)
                              )
                              .then(function() {
                                isDlgOpen = false;
                              })
                        };*/


                    },
                    controllerAs: 'vm'
                }

                $mdToast.show(toast);
            }
        }
    }

})();