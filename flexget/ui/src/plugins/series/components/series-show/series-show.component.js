(function () {
  'use strict';

  angular
    .module('flexget.plugins.series')
    .component('seriesShow', {
      templateUrl: 'plugins/series/components/series-show/series-show.tmpl.html',
      controllerAs: 'vm',
      controller: seriesShowController,
      bindings: {
        show: '<',
        forgetShow: '&'
      },
    });

    function seriesShowController($state, $mdDialog) {
      var vm = this;

      vm.gotoEpisodes = function() {
        $state.go('flexget.episodes', { id: vm.show.show_id });
      };

      vm.setBegin = function(ev) {
        $mdDialog.show({
          controller: 'seriesBeginController',
          controllerAs: 'vm',
          templateUrl: 'plugins/series/components/series-begin/series-begin.tmpl.html',
          locals: {
            showId: vm.show.show_id
          }
        }).then(function(data) {
          vm.show.begin_episode = data;
        }, function(err) {
          console.log(err);
        });
      }
    }
})();
