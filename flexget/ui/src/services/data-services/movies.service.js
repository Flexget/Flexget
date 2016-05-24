(function () {
    'use strict';

    angular.module('flexget.services')
        .factory('moviesService', moviesService);

    function moviesService($http, CacheFactory, errorService) {
        // If cache doesn't exist, create it
        if (!CacheFactory.get('moviesCache')) {
            CacheFactory.createCache('moviesCache');
        }

        var moviesCache = CacheFactory.get('moviesCache');

        return {
            getLists: getLists,
            deleteList: deleteList,
            getListMovies: getListMovies,
            deleteMovie: deleteMovie,
            createList: createList
        }

        function getLists() {
            return $http.get('/api/movie_list/')
                .then(getListsComplete)
                .catch(callFailed);

            function getListsComplete(response) {
                return response.data;
            }
        }

        function deleteList(listId) {
            return $http.delete('/api/movie_list/' + listId + '/')
                .then(deleteListComplete)
                .catch(callFailed);

            function deleteListComplete(response) {
                return;
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

        function deleteMovie(listId, movieId) {
            return $http.delete('/api/movie_list/' + listId + '/movies/' + movieId + '/')
                .then(deleteMovieComplete)
                .catch(callFailed);

            function deleteMovieComplete() {

                //TODO: Clear cache
                return;
            }
        }

        function createList(name) {
            return $http.post('/api/movie_list/', { name: name })
                .then(createListComplete)
                .catch(callFailed);

            function createListComplete(response) {
                return response.data;
            };
        };

        function callFailed(error) {
            //TODO: handle error

            console.log(error);

            errorService.showToast(error);
        }
    }
})();