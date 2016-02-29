(function () {
    'use strict';

    angular.module('flexget.directives')
        .controller('materialPaginationController', materialPaginationController);

      function materialPaginationController($scope) {
        var vm = this;

        vm.index = 0;
        vm.step = $scope.step;
        vm.totalPages = $scope.totalPages;

    /*vm.goto = function(index) {
      $scope.currentPage = vm.page[index];
    };

    vm.getoPre = function(){
      $scope.currentPage = vm.index;
      vm.index -= vm.step;
    };

    vm.getoNext = function(){
      vm.index += vm.step;
      $scope.currentPage = vm.index + 1;
    };

      vm.gotoFirst = function(){
        vm.index = 0;
        $scope.currentPage = 1;
      };

    vm.gotoLast = function(){
      vm.index = parseInt($scope.totalPages / vm.step) * vm.step;
      vm.index === $scope.totalPages ? vm.index = vm.index - vm.step : '';
      $scope.currentPage = $scope.totalPages;
    };*/

    /*$scope.$watch('currentPage', function() {
      $scope.gotoPage();
    });*/

    $scope.$watch('totalPages', function() {
      vm.init();
    });

    vm.init = function() {
      vm.stepInfo = (function() {
        var i, result = [];

        var lowest = Math.min(vm.step, vm.totalPages)



        for (i = 0; i < lowest; i++) {
          result.push(i)
        }
        return result;
      })();


      vm.page = (function() {
        var i, result = [];
        for (i = 1; i <= $scope.totalPages; i++) {
          result.push(i);
        }
        return result;
      })();
    };
  }
})();