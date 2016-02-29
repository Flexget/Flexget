(function () {
    'use strict';

    angular.module('flexget.plugins.profile')
        .controller('profileController', profileController);

    function profileController($http, Dialog, $state) {
        var vm = this;

        vm.title = 'Profile';
        vm.description = 'Profile Management';
        vm.password = "";

        vm.errorMessages = undefined; 

        vm.updatePassword = function() {
            $http.put('/api/user/', { password: vm.password }).success(function(data) {
                var options = {
                    title: "Password updated",
                    body: "Your password has been successfully updated.",
                    ok: "Close"
                }

                Dialog.open(options)
                .finally(function() {
                    $state.go('flexget.home');
                });
            }).error(function(error) {
                vm.Error = true;
                vm.errorMessages = error;

                console.log(vm.errorMessages);
                console.log(error);
            });
        }
    }

})();