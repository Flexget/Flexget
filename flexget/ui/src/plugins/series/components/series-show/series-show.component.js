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
        confirmDelete: '&'
      },
    });

    function seriesShowController($state, $mdDialog) {
      var vm = this;

      vm.gotoEpisodes = function() {
        $state.go('flexget.episodes', { id: vm.show.show_id });
      };

      vm.forgetSeries = function() {
        var confirm = $mdDialog.confirm()
          .title('Confirm forgetting show.')
          .htmlContent("Are you sure you want to completely forget <b>" + vm.show.show_name + "</b>?")
          .ok("Forget")
          .cancel("No");

        $mdDialog.show(confirm).then(function() {
          vm.confirmDelete();
        });
      }

    }
})();
