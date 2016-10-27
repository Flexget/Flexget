/* global angular */
(function () {
    'use strict';

    angular
        .module('plugins.movies')
        .factory('moviesService', moviesService);

    function moviesService($http, exception) {
        return {
            getLists: getLists,
            deleteList: deleteList,
            getListMovies: getListMovies,
            deleteMovie: deleteMovie,
            createList: createList,
            getMovieMetadata: getMovieMetadata,
            addMovieToList: addMovieToList,
            searchMovies: searchMovies
        };

        function getLists() {
            return $http.get('/api/movie_list/', {
                etagCache: true
            })
                .catch(callFailed);
        }

        function deleteList(listId) {
            return $http.delete('/api/movie_list/' + listId + '/')
                .catch(callFailed);
        }

        function getListMovies(listId, options) {
            return $http.get('/api/movie_list/' + listId + '/movies/', {
                params: options,
                etagCache: true
            })
                .catch(callFailed);
        }

        function deleteMovie(listId, movieId) {
            return $http.delete('/api/movie_list/' + listId + '/movies/' + movieId + '/')
                .catch(callFailed);
        }

        function createList(name) {
            return $http.post('/api/movie_list/', {
                name: name
            })
                .then(callCompleted)
                .catch(callFailed);
            
            function callCompleted(response) {
                return response.data;
            }
        }

        function getMovieMetadata(params) {
            return $http.get('/api/tmdb/movies/', {
                params: params,
                etagCache: true
            })
                .catch(callFailed);
        }

        function addMovieToList(listid, movie) {
            return $http.post('/api/movie_list/' + listid + '/movies/', movie)
                .catch(callFailed);
        }

        function searchMovies(searchText) {
            return $http.get('/api/imdb/search/' + searchText, {
                etagCache: true
            })
                .catch(callFailed);
        }

        function callFailed(error) {
            return exception.catcher(error);
        }
    }
}());