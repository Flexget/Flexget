(function () {
  'use strict';
  angular
  .module("flexget.plugins.movies")
  .component('moviesView', {
    templateUrl: 'plugins/movies/movies.tmpl.html',
    controllerAs: 'vm',
    controller: moviesController,
  });

  function moviesController($http, $mdDialog) {
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


    vm.deleteMovie = function(listid, movie) {

      var confirm = $mdDialog.confirm()
      .title('Confirm deleting movie')
      .htmlContent("Are you sure you want to forget this movie ?")
      .ok("Delete")
      .cancel("No");

      $mdDialog.show(confirm).then(function() {
        $http.delete('/api/movie_list/' + listid + '/movies/' + movie.id + '/')
        .success(function(data) {
          var index = vm.movies.indexOf(movie);
          vm.movies.splice(index, 1);
        }).error(function(error) {
          console.log(err);

          var errorDialog = $mdDialog.alert()
            .title("Something went wrong")
            .htmlContent("Oops, something went wrong when trying to forget <b>" + movie.title + "</b>:<br />" + error.message)
            .ok("Ok");

          $mdDialog.show(errorDialog);
        });
      });
    }

  }

})();
