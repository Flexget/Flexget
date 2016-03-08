(function () {
  'use strict';

  var logModule = angular.module('flexget.plugins.log', ['ui.grid', 'ui.grid.autoResize', 'ui.grid.autoScroll']);
  registerPlugin(logModule);

  logModule.run(function ($state, route, sideNav, toolBar) {
    route.register('log', '/log', 'log-view');
    sideNav.register('/log', 'Log', 'fa fa-file-text-o', 128);
    toolBar.registerButton('Log', 'fa fa-file-text-o', function () {
      $state.go('flexget.log')
    });
  });

})();
