(function () {
  'use strict';

  angular
  .module('flexget.plugins.movies')
  .component('movieEntry',{
    templateUrl: 'plugins/movies/components/movie-entry/movie-entry.tmpl.html',
    controller: movieEntryController,
    controllerAs: 'vm',
    bindings: {
      movie: '<',
      deleteMovie: '&'
    },
  });


  function movieEntryController ($http) {

    var vm = this;



    $http.get('/api/trakt/movie/', {
      params : {
        title: vm.movie.title,
        year : vm.movie.year
      }
    })
    .success(function (data) {
      vm.metadata = data;

    }).error(function (err) {
      console.error(err);
    })
  }

})();
