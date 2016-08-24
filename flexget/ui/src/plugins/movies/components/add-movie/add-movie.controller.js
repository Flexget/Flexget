/* global angular */
(function () {
    'use strict';

    angular
        .module('plugins.movies')
        .controller('addMovieController', addMovieController);

    function addMovieController(moviesService) {
        var vm = this;

        vm.currentList = vm.lists[vm.selectedlist].id;
        
        vm.addMovietoList = function (movie, list) {
            var movieObject = {
                movie_name: movie.name,
                movie_year: parseInt(movie.year),
                movie_identifiers: [
                    { imdb_id: movie.imdb_id }
                ]
            }
            moviesService.addMovieToList(list, movieObject)
        }
    }
}());