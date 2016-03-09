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
    }
})();
