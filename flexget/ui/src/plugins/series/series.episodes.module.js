(function () {
    'use strict';

    var seriesEpisodesModule = angular.module('flexget.plugins.series.episodes', []);
    registerPlugin(seriesEpisodesModule);

    seriesEpisodesModule.run(function ($state, route, sideNav, toolBar) {
        route.register('episodes', '/series/:id/episodes', 'episodesController', 'plugins/series/series.episodes.tmpl.html');
    });

})();