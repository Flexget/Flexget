(function () {
  'use strict';

  angular
    .module('flexget.plugins.execute')
    .component('executeInput', {
      templateUrl: 'plugins/execute/components/execute-input/execute-input.tmpl.html',
      controllerAs: 'vm',
      bindings: {
        options: '<',
        running: '<',
        execute: '<',
        tasksInput: '<',
        addTask: '<',
      },
    });
})();
