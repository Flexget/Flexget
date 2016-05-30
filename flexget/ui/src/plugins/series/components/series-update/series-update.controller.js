(function () {
    'use strict';

    angular
    .module('flexget.plugins.series')
    .controller('seriesUpdateController', seriesUpdateController)
    .directive('unique', uniqueDirective)

    function seriesUpdateController(showId, params, $mdDialog, $http) {
        var vm = this;

        //Copy so we don't override the original items
        vm.params = angular.copy(params);
        vm.newName = undefined;

        vm.cancel = function() {
            $mdDialog.hide();
        }

        vm.removeName = function(index) {
            vm.params.alternate_names.splice(index, 1);
        }

        vm.addName = function() {
            console.log('trying to add');
            if(vm.params.alternate_names.indexOf(vm.newName) == -1) {
                vm.params.alternate_names.push(vm.newName);
                vm.newName = undefined;
            }
        }

        vm.save = function() {
            if(!angular.equals(vm.params, params)) {
                $http.put('/api/series/' + showId, vm.params)
                .success(function(data) {
                    $mdDialog.hide(data);
                })
                .error(function(err) {
                    //TODO: Error handling
                    console.log(err);
                });
            } else {
                $mdDialog.hide();
            }
        }
    }

    function uniqueDirective() {
        return {
            restrict: 'A',
            require: 'ngModel',
            link: function(scope, element, attrs, ctrl) {
                ctrl.$validators.unique = function(modelValue, viewValue) {
                    if(scope.$eval(attrs.uniqueArray).indexOf(viewValue) == -1) {
                        console.log('ok');
                        return true;
                    }
                    return false;
                }
            }
        }
    }
})();
