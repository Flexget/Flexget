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
        vm.searchMovies = searchMovies;

        function activate() {
            getMovieLists();
        }

        vm.results = [];

        vm.typed = function(text) {
            //TODO: Close menu or update results?

            if(text.length >= 3) {
                searchMovies(text).then(function (results) {
                    vm.results = results;
                    vm.openSearchMenu();
                });
            }
        }

        vm.openSearchMenu = function () {
            var position = $mdPanel.newPanelPosition().relativeTo('.search-menu').addPanelPosition($mdPanel.xPosition.ALIGN_START, $mdPanel.yPosition.BELOW);

            var config = {
                attachTo: angular.element(document.body),
                controller: 'addMovieController',
                controllerAs: 'vm',
                templateUrl: 'plugins/movies/components/add-movie/add-movie.tmpl.html',
                panelClass: 'add-movie-panel',
                position: position,
                locals: {
                    foundmovies: vm.results,
                    lists: vm.lists,
                    selectedlist: vm.selectedlist
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