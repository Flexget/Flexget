(function () {
  'use strict';
  angular
    .module("flexget.plugins.movies")
    .component('moviesView', {
      templateUrl: 'plugins/movies/movies.tmpl.html',
      controllerAs: 'vm',
      controller: moviesController,
    });

  function moviesController($http) {
    var vm = this;

    vm.title = 'Movies';

    $http.get('/api/movie_list/').success(function(data) {
      console.log(data);
      vm.lists = data.movie_lists;
    }).error(function(err) {
      console.log(err);
    });


    vm.loadMovies = function(id) {
      console.log(id);
      $http.get('/api/movie_list/' + id + '/movies/')
      .success(function(data) {
        console.log(data);
        vm.movies = data.movies;
      }).error(function(err) {
        console.log(err);
      })
      console.log(id);
    }
    
  }

})();
