(function () {
    'use strict';

    var seriesModule = angular.module('flexget.plugins.series', []);
    registerPlugin(seriesModule);

    seriesModule.run(function ($state, route, sideNav, toolBar) {
        route.register('series', '/series', 'seriesController', 'plugins/series/series.tmpl.html');
        route.register('episodes', '/series/:id/episodes', 'episodesController', 'plugins/series/series.episodes.tmpl.html');

        sideNav.register('/series', 'Series', 'fa fa-tv', 128);
    });

})();