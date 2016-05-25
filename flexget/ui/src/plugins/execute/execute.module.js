(function () {
  'use strict';

  var executeModule = angular.module("flexget.plugins.execute", ['ui.grid', 'ui.grid.autoResize', 'angular-spinkit']);

  registerPlugin(executeModule);

  /*executeModule.run(function (route, sideNav) {
    route.register('execute', '/execute', 'execute-view');
    sideNav.register('/execute', 'Execute', 'fa fa-cog', 20);
   });*/

})();
