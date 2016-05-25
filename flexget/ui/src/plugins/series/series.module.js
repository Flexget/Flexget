(function () {
    'use strict';

    var seriesModule = angular.module('flexget.plugins.series', []);
    registerPlugin(seriesModule);

    /*seriesModule.run(function ($state, route, sideNav, toolBar) {
        route.register('series', '/series', 'series-view');
        route.register('episodes', '/series/:id/episodes', 'series-episodes-view');

        sideNav.register('/series', 'Series', 'fa fa-tv', 40);
    });*/

})();
