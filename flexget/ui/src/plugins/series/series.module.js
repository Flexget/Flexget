(function () {
    'use strict';

    var seriesModule = angular.module('flexget.plugins.series', []);
    registerPlugin(seriesModule);

    seriesModule.run(function ($state, route, sideNav, toolBar) {
        route.register('series', '/series', 'seriesController', 'plugins/series/series.tmpl.html');
        sideNav.register('/series', 'series', 'fa fa-tv', 128);
    });

})();