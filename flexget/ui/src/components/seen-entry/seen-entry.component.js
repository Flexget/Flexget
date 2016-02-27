(function () {
  'use strict';

  angular
    .module('flexget.components')
    .component('seenEntry', seenEntryComponent);

  function seenEntryComponent() {
  }

  var seenEntryComponent = {
    templateUrl: 'components/seen-entry/seen-entry.tmpl.thml',
    controllerAs: 'vm',
    controller: seenEntryController,
    bindings: {
      entry: '<',
    },
  }
})();
