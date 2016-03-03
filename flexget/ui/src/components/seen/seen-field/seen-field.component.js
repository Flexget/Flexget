(function () {
  'use strict';

  angular
    .module('flexget.components')
    .component('seenFields',{
      templateUrl: 'components/seen/seen-fields/seen-fields.tmpl.html',
      controllerAs: 'vm',
      controller: seenFieldsController,
      bindings: {
        fields: '<',
      },
    });

  function seenFieldsController() {
  }
})();
