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
                tabIndex: '<'
            }
        });


    function movieListController($mdDialog, $sce, moviesService, $rootScope) {
        var vm = this;

        vm.$onInit = activate;
        vm.$onDestroy = destroy;
        vm.tabSelected = tabSelected;
        vm.tabDeselected = tabDeselected;
        vm.loadMovies = loadMovies;
        vm.deleteMovie = deleteMovie;
        vm.updateListPage = updateListPage;

        var listener;
        var currentTab = false;

        var options = {
            page: 1,
            'page_size': 10,
            order: 'asc'
        };

        function tabSelected() {
            loadMovies();
            currentTab = true;
        }

        function tabDeselected() {
            currentTab = false;
        }
        
        function activate() {
            //Hack to make the movies from the first tab load (md-on-select not firing for initial tab)
            if (vm.tabIndex === 0) {
                loadMovies();
                currentTab = true;
            }

            listener = $rootScope.$on('movie-added-list:' + vm.list.id, function () {
                if (currentTab) {
                    loadMovies();
                }
            });
        }

        function destroy() {
            if (listener) {
                listener();
            }
        }

        function loadMovies() {
            moviesService.getListMovies(vm.list.id, options)
                .then(function (data) {
                    vm.movies = data.movies;

                    vm.currentPage = data.page;
                    vm.totalMovies = data.total_number_of_movies;
                    vm.pageSize = data.number_of_movies;
                });
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
                        var index = vm.movies.indexOf(movie);
                        vm.movies.splice(index, 1);
                    });
            });
        }

        //Call from the pagination to update the page to the selected page
        function updateListPage (index) {
            options.page = index;

            loadMovies();
        }
    }
}());
