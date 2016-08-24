/* global angular */
(function () {
    'use strict';

    angular
        .module('plugins.movies')
        .component('moviesView', {
            templateUrl: 'plugins/movies/movies.tmpl.html',
            controllerAs: 'vm',
            controller: moviesController
        });

    function moviesController($mdDialog, $mdPanel, $sce, moviesService) {
        var vm = this;

        vm.lists = [];
        vm.$onInit = activate;
        vm.deleteMovieList = deleteMovieList;
        vm.newList = newList;
        vm.addMovie = addMovie;
        vm.searchMovies = searchMovies;
        vm.movieSelected = movieSelected;

        function activate() {
            getMovieLists();
        }

        vm.typed = function(text) {
            //TODO: Search
            //TODO: Close menu or update results?

            if(text.length >= 3) {

                searchMovies(text).then(function(results) {
                    vm.openSearchMenu(results);
                });
            }

            //text.length >= 3 ? vm.openSearchMenu() : null;
        }

        vm.openSearchMenu = function(results) {
            var position = $mdPanel.newPanelPosition().relativeTo('.search-menu').addPanelPosition($mdPanel.xPosition.ALIGN_START, $mdPanel.yPosition.BELOW);

            var config = {
                attachTo: angular.element(document.body),
                controller: function(mdPanelRef) {
                    var vm = this;
                },
                controllerAs: 'vm',
                templateUrl: 'plugins/movies/search.tmpl.html',
                panelClass: 'add-movie-panel',
                position: position,
                locals: {
                    'foundmovies': results,
                    'lists': vm.lists
                },
                clickOutsideToClose: true,
                escapeToClose: true,
                focusOnOpen: false,
                zIndex: 2
            }

            $mdPanel.open(config);
        }

        function getMovieLists() {
            moviesService.getLists().then(function (data) {
                vm.lists = data.movie_lists;
            });
        }

        function deleteMovieList(list) {
            var confirm = $mdDialog.confirm()
                .title('Confirm deleting movie list.')
                .htmlContent($sce.trustAsHtml('Are you sure you want to delete the movie list <b>' + list.name + '</b>?'))
                .ok('Forget')
                .cancel('No');

            //Actually show the confirmation dialog and place a call to DELETE when confirmed
            $mdDialog.show(confirm).then(function () {
                moviesService.deleteList(list.id)
                    .then(function () {
                        var index = vm.lists.indexOf(list);
                        vm.lists.splice(index, 1);
                    });
            });
        }

        // Function to prevent a movie from being selected in the autocomplete
        function movieSelected($event) {
            $event.preventDefault();
            $event.stopPropagation();
        }

        function addMovie(movie, list) {
            moviesService.addMovieToList(list, movie)
        }

        function searchMovies(searchText) {
            var lowercaseSearchText = angular.lowercase(searchText);
            return moviesService.searchMovies(lowercaseSearchText);
        }

        function newList($event) {
            $event.preventDefault();
            $event.stopPropagation();

            var listNames = vm.lists.map(function (list) {
                return list.name;
            });

            var dialog = {
                template: '<new-list lists="vm.lists"></new-list>',
                locals: {
                    lists: listNames
                },
                bindToController: true,
                controllerAs: 'vm',
                controller: function () { }
            };

            $mdDialog.show(dialog).then(function (newList) {
                if (newList) {
                    vm.lists.push(newList);
                }
            });
        }
    }
}());