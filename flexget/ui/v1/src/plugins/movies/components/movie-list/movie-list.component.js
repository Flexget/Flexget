/* global angular */
(function () {
    'use strict';

    angular
        .module('plugins.movies')
        .component('movieList', {
            templateUrl: 'plugins/movies/components/movie-list/movie-list.tmpl.html',
            controller: movieListController,
            controllerAs: 'vm',
            bindings: {
                list: '<',
                deleteMovieList: '&',
                tabIndex: '<',
                linkHeader: '=',
                currentPage: '='
            }
        });


    function movieListController($mdDialog, $sce, moviesService, $rootScope) {
        var vm = this;

        vm.$onInit = activate;
        vm.$onDestroy = destroy;
        vm.tabSelected = tabSelected;
        vm.tabDeselected = tabDeselected;
        vm.deleteMovie = deleteMovie;

        var loadMoviesListener, addMovieToListListener;
        var options = {
            'per_page': 10,
            order: 'asc'
        };

        function tabSelected() {
            loadMovies(1);
            loadMoviesListener = $rootScope.$on('load-movies', function (event, args) {
                loadMovies(args.page);
            });
            addMovieToListListener = $rootScope.$on('movie-added-list:' + vm.list.id, function () {
                loadMovies(vm.currentPage);
            })
        }

        function tabDeselected() {
            loadMoviesListener();
            addMovieToListListener();
        }
        
        function activate() {
            //Hack to make the movies from the first tab load (md-on-select not firing for initial tab)
            if (vm.tabIndex === 0) {
                tabSelected();
            }
        }

        function destroy() {
            loadMoviesListener ? loadMoviesListener() : null;
            addMovieToListListener ? addMovieToListListener() : null;
        }

        function loadMovies(page) {
            options.page = page;
            moviesService.getListMovies(vm.list.id, options)
                .then(setMovies)
                .cached(setMovies)
                .finally(function () {
                    vm.currentPage = options.page;
                });
        }

        function setMovies(response) {
            vm.movies = response.data;
            vm.linkHeader = response.headers().link;
        }

        function deleteMovie(list, movie) {
            var confirm = $mdDialog.confirm()
                .title('Confirm deleting movie from list.')
                .htmlContent($sce.trustAsHtml('Are you sure you want to delete the movie <b>' + movie.title + '</b> from list <b>' + list.name + '</b>?'))
                .ok('Forget')
                .cancel('No');

            $mdDialog.show(confirm).then(function () {
                moviesService.deleteMovie(list.id, movie.id)
                    .then(function () {
                        loadMovies(vm.currentPage);
                    });
            });
        }
    }
}());
