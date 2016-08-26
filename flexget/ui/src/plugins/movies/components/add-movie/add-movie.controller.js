/* global angular */
(function () {
    'use strict';

    angular
        .module('plugins.movies')
        .controller('addMovieController', addMovieController);

    function addMovieController(moviesService, mdPanelRef, $scope, $timeout) {
        var vm = this;

        $scope.$watch(function () {
            return mdPanelRef.config.locals.searchtext;
        }, function (newValue, oldValue) {
            vm.searchtext = mdPanelRef.config.locals.searchtext;
            checkSearch(newValue);
        });
        
        function checkSearch(val) {
            $timeout(function () {
                if (val === vm.searchtext) {
                    searchMovies(val).then(function (data) {
                        vm.foundMovies = data;
                    })
                }
            }, 1000);
        }

        function searchMovies(searchText) {
            var lowercaseSearchText = angular.lowercase(searchText);
            return moviesService.searchMovies(lowercaseSearchText);
        }

        /*vm.currentList = vm.lists[vm.selectedlist].id;
        
        vm.addMovietoList = function (movie, list) {
            var movieObject = {
                movie_name: movie.name,
                movie_year: parseInt(movie.year),
                movie_identifiers: [
                    { imdb_id: movie.imdb_id }
                ]
            }
            moviesService.addMovieToList(list, movieObject)
        }*/
    }
}());