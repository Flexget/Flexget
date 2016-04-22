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

    getMetadata();


    function getMetadata() {

      var params = {
        title: vm.movie.title,
        year : vm.movie.year
      }

      vm.movie.movies_list_ids.forEach(function (id) {
        var newid = {};
        newid[id.id_name] = id.id_value;
        params = $.extend(params, newid);
      })


      $http.get('/api/trakt/movie/', {
        params: params,
        cache: true
      })
      .success(function (data) {

        vm.metadata = data;


      }).error(function (err) {
        console.error(err);
      })
    }
  }



})();
