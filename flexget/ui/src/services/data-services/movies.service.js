(function () {
    'use strict';

    angular.module('flexget.services')
        .factory('moviesService', moviesService);

    function moviesService($http, CacheFactory, $mdDialog, errorService) {
        // If cache doesn't exist, create it
        if (!CacheFactory.get('moviesCache')) {
            CacheFactory.createCache('moviesCache');
        }

        var moviesCache = CacheFactory.get('moviesCache');

        return {
            getLists: getLists,
            getListMovies: getListMovies,
            deleteMovie: deleteMovie
        }

        function getLists() {
            return $http.get('/api/movie_list/')
                .then(getListsComplete)
                .catch(callFailed);

            function getListsComplete(response) {
                return response.data;
            }
        }

        function getListMovies(listId, options) {
            return $http.get('/api/movie_list/' + listId + '/movies/', { params: options })
                .then(getListMoviesComplete)
                .catch(callFailed);

            function getListMoviesComplete(response) {
                return response.data;
            }
        }

        function deleteMovie(listId, movie) {
            return $http.delete('/api/movie_list/' + listid + '/movies/' + movie.id + '/')
                .then(deleteMovieComplete)
                .catch(callFailed);

            function deleteMovieComplete() {

                //TODO: Clear cache
                return;
            }
        }


        function callFailed(error) {
            //TODO: handle error

            console.log(error);

            errorService.showToast(error);
        }
    }
})();