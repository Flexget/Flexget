(function () {
    'use strict';

    var configModule = angular.module("flexget.plugins.config", ['ui.ace', 'ab-base64', 'angular-cache']);

    registerPlugin(configModule);

    configModule.run(function (route, sideNav) {
        route.register('config', '/config', 'config-view');
        sideNav.register('/config', 'Config', 'fa fa-pencil', 15);
    });

})();
