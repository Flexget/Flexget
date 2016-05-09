(function () {
    'use strict';

    var moviesModule = angular.module("flexget.plugins.movies", []);

    registerPlugin(moviesModule);

    moviesModule.run(function (route, sideNav) {
        route.register('movies', '/movies', 'movies-view');
        sideNav.register('/movies', 'Movies', 'fa fa-film', 50);
    });

})();
