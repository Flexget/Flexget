(function () {
    'use strict';

    angular.module('flexget.plugins.profile')
        .controller('profileController', profileController);

    function profileController($http) {
        var vm = this;

        vm.title = 'Profile';
        vm.description = 'Profile Management';
        vm.password = "";

        vm.errorMessages = undefined; 

        vm.updatePassword = function() {
            /*vm.errorMessage = {
            "firstError": {
                "testing": "Bullshit"
            }
        };;*/
            $http.put('/api/user/', { password: vm.password }).success(function(data) {
                console.log(data);
            }).error(function(error) {
                vm.Error = true;
                vm.errorMessages = error;

                console.log(vm.errorMessages);
                console.log(error);
            });
        }
    }

})();