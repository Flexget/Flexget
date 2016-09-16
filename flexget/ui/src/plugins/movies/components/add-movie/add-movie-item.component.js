/* global angular */
(function () {
    'use strict';

    angular
        .module('plugins.movies')
        .component('addMovieItem', {
            templateUrl: 'plugins/movies/components/add-movie/add-movie-item.tmpl.html',
            controllerAs: 'vm',
            controller: addMovieController,
            bindings: {
                movie: '<',
                lists: '<',
                selectedList: '<',
                addMovieToList: '&'
            },
            transclude: true
        });

    function addMovieController() {
        var vm = this;

        vm.addMovie = addMovie;

        function addMovie() {
            vm.addMovieToList({
                movie: vm.movie,
                list: vm.selectedList
            });
        }
    }
}());