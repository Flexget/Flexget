(function () {
  'use strict';

angular
    .module('flexget.plugins.series')
    .controller('seriesUpdateController', seriesUpdateController)

    function seriesUpdateController(showId, params, $mdDialog, $http) {
      var vm = this;

      //Copy so we don't override the original items
      vm.params = angular.copy(params);

      vm.cancel = function() {
        //TODO: Warn changes will not be saved
        $mdDialog.cancel();
      }

      vm.removeName = function(index) {
        vm.params.alternate_names.splice(index, 1);
      }

      vm.addName = function(name) {
        vm.params.alternate_names.push(name);
      }

      vm.save = function() {
        $http.put('/api/series/' + showId, vm.params)
          .success(function(data) {
            $mdDialog.hide(data);
          })
          .error(function(err) {
            //TODO: Error handling
            console.log(err);
          });
      }
    }
  })();