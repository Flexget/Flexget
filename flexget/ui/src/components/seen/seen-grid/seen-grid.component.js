(function () {
  'use strict';

  angular
    .module('flexget.components')
    .component('seenGrid',{
      templateUrl: 'components/seen/seen-grid/seen-grid.tmpl.html',
      controllerAs: 'vm',
      controller: seenGridController,
      bindings: {
        entries: '<',
      },
    });

  function seenGridController() {
  }
})();
