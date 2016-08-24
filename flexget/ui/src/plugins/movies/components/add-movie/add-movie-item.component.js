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
            }
        });

    function addMovieController() {
        var vm = this;

        vm.addMovie = addMovie;

        function addMovie() {
            console.log(vm);
            vm.addMovieToList({
                movie: vm.movie,
                list: vm.selectedList
            });
        }
    }
}());