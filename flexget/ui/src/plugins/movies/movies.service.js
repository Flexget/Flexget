/* global angular */
(function () {
    'use strict';

    angular
        .module('plugins.movies')
        .factory('moviesService', moviesService);

    function moviesService($http, /*CacheFactory,*/ exception) {
        // If cache doesn't exist, create it

        //TODO: Enable cache
        /*if (!CacheFactory.get('moviesCache')) {
            CacheFactory.createCache('moviesCache');
        }

        var moviesCache = CacheFactory.get('moviesCache');*/

        return {
            getLists: getLists,
            deleteList: deleteList,
            getListMovies: getListMovies,
            deleteMovie: deleteMovie,
            createList: createList,
            getMovieMetadata: getMovieMetadata,
            addMovieToList: addMovieToList
        };

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

            function deleteListComplete() {
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
            }
        }

        function getMovieMetadata(title, params) {
            return $http.get('/api/trakt/movies/' + title + '/', {
                params: params,
                cache: true
            })
                .then(getMovieMetadataComplete)
                .catch(callFailed);

            function getMovieMetadataComplete(response) {
                return response.data;
            }
        }

        function addMovieToList(listid, movie) {
            return $http.post('/api/movie_list/' + listid + '/movies/', movie)
                .then(addMovieToListComplete)
                .catch(callFailed);

            function addMovieToListComplete(response) {
                return;
            }
        }

        function callFailed(error) {
            return exception.catcher(error);
        }
    }
}());