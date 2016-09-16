/* global angular */
(function () {
    'use strict';

    angular
        .module('plugins.movies')
        .factory('addMovieService', addMovieService);

    function addMovieService() {
        var searchWatch;

        return {
            setWatcher: setWatcher,
            clearWatcher: clearWatcher
        };

        function setWatcher(watch) {
            searchWatch = watch;
        }

        function clearWatcher() {
            if (searchWatch) {
                searchWatch();
            }    
        }
    }
})();