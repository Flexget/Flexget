(function () {
    'use strict';

    var historyModule = angular.module("flexget.plugins.history", ['angular.filter']);

    registerPlugin(historyModule);

    historyModule.run(function (route, sideNav) {
        route.register('history', '/history', 'historyController', 'plugins/history/history.tmpl.html');
        sideNav.register('/history', 'History', 'fa fa-history', 128);
    });

})();