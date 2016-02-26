(function () {
    'use strict';

    angular.module('flexget.plugins.movies')
        .controller('moviesController', moviesController);

    function moviesController($scope, $http, Dialog) {
        var vm = this;        

        var params = {
            page: 1,
            max: 10
        }

        var DialogOptions = {
            title: "Loading failed",
            ok: "Ok"
        }

        function setMoviesList() {
            $http.get('/api/movie_queue', { params: params })
                .success(function(data) {
                    vm.movies = data.movies;
                }).error(function(error) {
                    vm.movies = [];
                    DialogOptions.body = "Oops, something went wrong when trying to download the movies list: " + error.message;
                    Dialog.open(DialogOptions);
                });
        }

        vm.getDownloaded = function() {
            params = {
                page: 1,
                max: 10,
                is_downloaded: true
            }
            setMoviesList();
        }

        vm.getAll = function() {
            params = {
                page: 1,
                max: 10,
                is_downloaded: undefined
            }
            setMoviesList();
        }

        vm.getNotDownloaded = function() {
            params = {
                page: 1,
                max: 10,
                is_downloaded: false
            }
            setMoviesList();
        }

        vm.tabs = [
            {
                label: "All",
                action: vm.getAll
            },
            {
                label: "Downloaded",
                action: vm.getDownloaded
            },
            {
                label: "Not Downloaded",
                action: vm.getNotDownloaded
            }
        ]
    }

})
();