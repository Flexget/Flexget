(function () {
  'use strict';

  angular
    .module('flexget.components')
    .component('seenEntry',{
      templateUrl: 'components/seen/seen-entry/seen-entry.tmpl.html',
      controllerAs: 'vm',
      controller: seenEntryController,
      bindings: {
        entry: '<',
      },
    });

  function seenEntryController() {
  }
})();
