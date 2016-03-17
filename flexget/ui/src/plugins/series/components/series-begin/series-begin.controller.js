(function () {
  'use strict';

angular
    .module('flexget.plugins.series')
    .controller('seriesBeginController', seriesBeginController)

    function seriesBeginController(showId, $mdDialog, $http) {
      var vm = this;

      vm.cancel = function() {
        $mdDialog.cancel();
      }

      vm.save = function() {
        var params = {
          episode_identifier: vm.begin
        }

        $http.put('/api/series/' + showId, params)
          .success(function(data) {
            console.log(data);
            $mdDialog.hide(data.begin_episode);
          })
          .error(function(err) {
            console.log(err);
          });

        //TODO: Save and close dialog
      }
    }
  })();