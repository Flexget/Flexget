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

    function moviesController($document, $mdDialog, $mdPanel, $sce, $scope, addMovieService, moviesService) {
        var vm = this;

        vm.lists = [];
        vm.$onInit = activate;
        vm.deleteList = deleteList;
        vm.newList = newList;
        vm.searchMovies = searchMovies;
        vm.loadMovies = loadMovies;

        vm.searchtext = "";

        function activate() {
            getMovieLists();
        }

        var position = $mdPanel.newPanelPosition().relativeTo('.search-menu').addPanelPosition($mdPanel.xPosition.ALIGN_END, $mdPanel.yPosition.BELOW);
        var panelConfig = {
            attachTo: angular.element($document[0].body),
            controller: 'addMovieController',
            controllerAs: 'vm',
            templateUrl: 'plugins/movies/components/add-movie/add-movie.tmpl.html',
            panelClass: 'add-movie-panel',
            position: position,
            locals: {},
            clickOutsideToClose: true,
            escapeToClose: true,
            focusOnOpen: false,
            zIndex: 2,
            onRemoving: addMovieService.clearWatcher,
            id: 'addMoviePanel'
        };
        
        function searchMovies() {
            panelConfig.locals.searchtext = vm.searchtext;
            panelConfig.locals.lists = vm.lists;
            panelConfig.locals.selectedlist = vm.selectedlist;

            $mdPanel.open(panelConfig);
        }

        function getMovieLists() {
            moviesService.getLists()
                .then(setLists)
                .cached(setLists);
        }
        
        function setLists(response) {
            vm.lists = response.data;
        }

        function deleteList($event, list) {
            $event.preventDefault();
            $event.stopPropagation();

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

        function loadMovies(data) {
            $scope.$emit('load-movies', { page: data });
        }
    }
}());