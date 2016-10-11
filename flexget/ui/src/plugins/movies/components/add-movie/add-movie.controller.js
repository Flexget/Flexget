/* global angular */
(function () {
    'use strict';

    angular
        .module('plugins.movies')
        .controller('addMovieController', addMovieController);

    function addMovieController($mdPanel, $scope, $timeout, addMovieService, mdPanelRef, moviesService) {
        var vm = this;

        vm.panelRef = mdPanelRef.config.locals;
        delete vm.panelRef.mdPanelRef; //Remove circular reference to self

        vm.loading = true;

        var searchWatch = $scope.$watch(function () {
            return mdPanelRef.config.locals.searchtext;
        }, function (newValue) {
            vm.searchtext = mdPanelRef.config.locals.searchtext;
            checkSearch(newValue);
        });
        
        addMovieService.setWatcher(searchWatch);
        
        function checkSearch(val) {
            $timeout(function () {
                if (val === vm.searchtext) {
                    vm.loading = true;
                    
                    updatePosition();

                    var lowercaseSearchText = angular.lowercase(val);
                    moviesService.searchMovies(lowercaseSearchText)
                        .then(setFoundMovies)
                        .cached(setFoundMovies);
                }
            }, 1000);
        }

        function setFoundMovies(response) {
            vm.foundMovies = response.data;
            vm.loading = false;
            updatePosition();
        }

        function updatePosition() {
            $timeout(function () {
                mdPanelRef.updatePosition($mdPanel.newPanelPosition().relativeTo('.search-menu').addPanelPosition($mdPanel.xPosition.ALIGN_END, $mdPanel.yPosition.BELOW));
            }, 0);
        }

        function searchMovies(searchText) {
            var lowercaseSearchText = angular.lowercase(searchText);
            return moviesService.searchMovies(lowercaseSearchText);
        }

        vm.currentList = vm.panelRef.lists[vm.panelRef.selectedlist].id;
        
        vm.addMovietoList = function (movie, list) {
            var movieObject = {
                movie_name: movie.name,
                movie_year: parseInt(movie.year) || undefined,
                movie_identifiers: [
                    { imdb_id: movie.imdb_id }
                ]
            }
            moviesService.addMovieToList(list, movieObject).then(function () {
                $scope.$emit('movie-added-list:' + list);
            });
        }
    }
}());