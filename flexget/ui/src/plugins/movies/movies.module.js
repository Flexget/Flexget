(function () {
    'use strict';

    var moviesModule = angular.module('flexget.plugins.movies', []);
    registerPlugin(moviesModule);

    moviesModule.run(function ($state, route, sideNav, toolBar) {
        route.register('movies', '/movies', 'moviesController', 'plugins/movies/movies.tmpl.html');
        sideNav.register('/movies', 'Movies', 'fa fa-list', 128);
    });

})();