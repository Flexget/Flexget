(function () {
    'use strict';

    angular.module('flexget.plugins.movies')
        .filter('moviesListIdsFilter', moviesListIdsFilter);

    function moviesListIdsFilter() {
        var moviesListIds = {
            imdb_id: "IMDB",
            trakt_movie_id: "Trakt",
            tmdb_id: "TMDB"
        };

        return function (id) {
            if (id in moviesListIds) {
                return moviesListIds[id]
            } else {
                return "Unknown Provider: " + id;
            }
        };
    }

})();