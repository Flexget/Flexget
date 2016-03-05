(function () {
  'use strict';

  angular
    .module('flexget.plugins.log')
    .component('logHeader', {
      templateUrl: 'plugins/log/components/log-header/log-header.tmpl.html',
      controllerAs: 'vm',
      bindings: {
        status: '<',
        filter: '<',
        refresh: '<',
        refreshOpts: '<',
        toggle: '<',
        logStream: '<',
      },
    });
})();
