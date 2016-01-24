(function () {
    'use strict';

    var executeModule = angular.module("flexget.plugins.execute", ['ui.grid', 'ui.grid.autoResize', 'angular-spinkit']);

    registerPlugin(executeModule);

    executeModule.run(function (route, sideNav) {
        route.register('execute', '/execute', 'executeController', 'plugins/execute/execute.tmpl.html');
        sideNav.register('/execute', 'Execute', 'fa fa-cog', 128);
    });

})();