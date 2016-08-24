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
            text.length >= 3 ? vm.openSearchMenu() : null;
        }
    
    let foundmovies = [
  {
    "imdb_id": "tt0119468",
    "match": 1.045,
    "name": "Kiss the Girls",
    "thumbnail": "http://ia.media-imdb.com/images/M/MV5BMTc4MTkwNzI5M15BMl5BanBnXkFtZTYwNjk5NjU5._V1_UX32_CR0,0,32,44_AL_.jpg",
    "url": "http://www.imdb.com/title/tt0119468/",
    "year": "1997"
  },
  {
    "imdb_id": "tt1999121",
    "match": 1.01,
    "name": "Collector",
    "thumbnail": "http://ia.media-imdb.com/images/M/MV5BMDBhYjI4NjMtMjM0Yi00MTgzLWI1ZWItMWVhN2E1MjRjZTNkXkEyXkFqcGdeQXVyMjkxNzQ1NDI@._V1_UX32_CR0,0,32,44_AL_.jpg",
    "url": "http://www.imdb.com/title/tt1999121/",
    "year": "2011"
  },
  {
    "imdb_id": "tt1132285",
    "match": 0.9974999999999999,
    "name": "The Factory",
    "thumbnail": "http://ia.media-imdb.com/images/M/MV5BMTU3Mjk5MDk3OF5BMl5BanBnXkFtZTcwNjQ3MzEwOQ@@._V1_UY44_CR1,0,32,44_AL_.jpg",
    "url": "http://www.imdb.com/title/tt1132285/",
    "year": "2012"
  },
  {
    "imdb_id": "tt5031998",
    "match": 0.9816666666666667,
    "name": "Kollektor",
    "thumbnail": "http://ia.media-imdb.com/images/M/MV5BMmQwNTY5NTYtNjljNy00YWFkLTk0OTktY2IxOWIwZDMyZWI4XkEyXkFqcGdeQXVyMTAxNTgxMjc@._V1_UX32_CR0,0,32,44_AL_.jpg",
    "url": "http://www.imdb.com/title/tt5031998/",
    "year": "2016"
  },
  {
    "imdb_id": "tt0476646",
    "match": 0.9529411764705882,
    "name": "Collectors",
    "thumbnail": "http://ia.media-imdb.com/images/M/MV5BMTg5Njg0Mjk4MV5BMl5BanBnXkFtZTgwOTc2MDA2MDE@._V1_UY44_CR17,0,32,44_AL_.jpg",
    "url": "http://www.imdb.com/title/tt0476646/",
    "year": "2000"
  },
  {
    "imdb_id": "tt0844479",
    "match": 0.8386363636363636,
    "name": "The Collector",
    "thumbnail": "http://ia.media-imdb.com/images/M/MV5BMTQ4NTU3OTE3OF5BMl5BanBnXkFtZTcwNTkxMjA3Mg@@._V1_UX32_CR0,0,32,44_AL_.jpg",
    "url": "http://www.imdb.com/title/tt0844479/",
    "year": "2009"
  },
  {
    "imdb_id": "tt0059043",
    "match": 0.8345454545454546,
    "name": "The Collector",
    "thumbnail": "http://ia.media-imdb.com/images/M/MV5BMWI4YmIwZjgtYmFkMS00YWJlLWFhYzMtYjljZTdkYzU3MGNhXkEyXkFqcGdeQXVyMjI4MjA5MzA@._V1_UX32_CR0,0,32,44_AL_.jpg",
    "url": "http://www.imdb.com/title/tt0059043/",
    "year": "1965"
  },
  {
    "imdb_id": "tt0119769",
    "match": 0.8232954545454547,
    "name": "The Collector",
    "thumbnail": "http://ia.media-imdb.com/images/M/MV5BODlmNDE2MjItMDJmMS00NDg4LWJlYmQtNDIwZmY0YWI5NTFhXkEyXkFqcGdeQXVyNjU5MTE2MDg@._V1_UY44_CR16,0,32,44_AL_.jpg",
    "url": "http://www.imdb.com/title/tt0119769/",
    "year": "1997"
  },
  {
    "imdb_id": "tt2879218",
    "match": 0.8219008264462812,
    "name": "The Collector",
    "thumbnail": "http://ia.media-imdb.com/images/G/01/imdb/images/nopicture/32x44/film-3119741174._CB282925985_.png",
    "url": "http://www.imdb.com/title/tt2879218/",
    "year": "2012"
  },
  {
    "imdb_id": "tt1754611",
    "match": 0.8217391304347826,
    "name": "The Collector",
    "thumbnail": "http://ia.media-imdb.com/images/M/MV5BMTg3MzEzNDk1MF5BMl5BanBnXkFtZTgwNTc5NjE3NjE@._V1_UY44_CR0,0,32,44_AL_.jpg",
    "url": "http://www.imdb.com/title/tt1754611/",
    "year": "2006"
  },
  {
    "imdb_id": "tt2369375",
    "match": 0.8214545454545455,
    "name": "The Collector",
    "thumbnail": "http://ia.media-imdb.com/images/G/01/imdb/images/nopicture/32x44/film-3119741174._CB282925985_.png",
    "url": "http://www.imdb.com/title/tt2369375/",
    "year": "2013"
  },
  {
    "imdb_id": "tt3286664",
    "match": 0.8199604743083005,
    "name": "The Collector",
    "thumbnail": "http://ia.media-imdb.com/images/G/01/imdb/images/nopicture/32x44/film-3119741174._CB282925985_.png",
    "url": "http://www.imdb.com/title/tt3286664/"
  },
  {
    "imdb_id": "tt0174557",
    "match": 0.7881987577639752,
    "name": "The Collectors",
    "thumbnail": "http://ia.media-imdb.com/images/M/MV5BMTU5NjE3MjMwOF5BMl5BanBnXkFtZTYwNTI1MTI5._V1_UX32_CR0,0,32,44_AL_.jpg",
    "url": "http://www.imdb.com/title/tt0174557/",
    "year": "1999"
  },
  {
    "imdb_id": "tt0383996",
    "match": 0.7865217391304348,
    "name": "The Collectors",
    "thumbnail": "http://ia.media-imdb.com/images/M/MV5BMjEyNjI5MzY1Ml5BMl5BanBnXkFtZTgwNjMxMDA2MDE@._V1_UY44_CR1,0,32,44_AL_.jpg",
    "url": "http://www.imdb.com/title/tt0383996/",
    "year": "2003"
  },
  {
    "imdb_id": "tt1112661",
    "match": 0.7849104859335039,
    "name": "The Collectors",
    "thumbnail": "http://ia.media-imdb.com/images/M/MV5BMTM2MjI3NDMzMV5BMl5BanBnXkFtZTcwODk5NjQ5Ng@@._V1_UY44_CR1,0,32,44_AL_.jpg",
    "url": "http://www.imdb.com/title/tt1112661/",
    "year": "2007"
  },
  {
    "imdb_id": "tt1859599",
    "match": 0.7841739130434783,
    "name": "The Collectors",
    "thumbnail": "http://ia.media-imdb.com/images/G/01/imdb/images/nopicture/32x44/film-3119741174._CB282925985_.png",
    "url": "http://www.imdb.com/title/tt1859599/",
    "year": "2011"
  },
  {
    "imdb_id": "tt2187089",
    "match": 0.7217560975609756,
    "name": "Statue Collector",
    "thumbnail": "http://ia.media-imdb.com/images/M/MV5BMzgzNzY0N2MtNGNkMC00NGU4LWExZjUtMjlkN2RiZThkODMxXkEyXkFqcGdeQXVyMjM4ODgxOQ@@._V1_UY44_CR17,0,32,44_AL_.jpg",
    "url": "http://www.imdb.com/title/tt2187089/"
  },
  {
    "imdb_id": "tt1748227",
    "match": 0.7033816425120772,
    "name": "The Collection",
    "thumbnail": "http://ia.media-imdb.com/images/M/MV5BODQ0MDgzNDA0NV5BMl5BanBnXkFtZTcwNDM4MDQ1OA@@._V1_UX32_CR0,0,32,44_AL_.jpg",
    "url": "http://www.imdb.com/title/tt1748227/",
    "year": "2012"
  }
];

        vm.openSearchMenu = function() {
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
                    'foundmovies': foundmovies,
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