(function () {
  'use strict';

  angular
    .module('flexget.plugins.execute')
    .component('executeStream', {
      templateUrl: 'plugins/execute/components/execute-stream/execute-stream.tmpl.html',
      controllerAs: 'vm',
      bindings: {
        stream: '<',
        running: '<',
        clear: '<',
      },
    });
});