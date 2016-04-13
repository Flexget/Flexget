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
      vm.lists = data.movie_lists;

      //Hack to load movies from first list, because md-on-select does not fire on initial selection
      vm.loadMovies(vm.lists[0].id);
    }).error(function(err) {
      console.log(err);
    });


    vm.loadMovies = function(id) {
      $http.get('/api/movie_list/' + id + '/movies/')
      .success(function(data) {
        vm.movies = data.movies;
      }).error(function(err) {
        console.log(err);
      })
    }
    
  }

})();
