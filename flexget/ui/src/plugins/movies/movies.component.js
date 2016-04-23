(function () {
  'use strict';
  angular
  .module("flexget.plugins.movies")
  .component('moviesView', {
    templateUrl: 'plugins/movies/movies.tmpl.html',
    controllerAs: 'vm',
    controller: moviesController,
  });

  function moviesController($http, $mdDialog, $scope) {
    var vm = this;

    var options = {
      page: 1,
      page_size: 10
    }

    vm.title = 'Movies';

    $http.get('/api/movie_list/').success(function(data) {
      vm.lists = data.movie_lists;
    }).error(function(err) {
      console.log(err);
    });

    //Call from the pagination to update the page to the selected page
    vm.updateListPage = function(index) {
      options.page = index;

      loadMovies();
    }

    $scope.$watch(function() {
      return vm.selectedList;
    }, function(newValue, oldValue) {
      if(newValue != oldValue) {
        loadMovies();
      }
    });

    function loadMovies() {
      var listId = vm.lists[vm.selectedList].id;

      $http.get('/api/movie_list/' + listId + '/movies/', { params: options })
      .success(function(data) {

        vm.movies = data.movies;

        vm.currentPage = data.page;
        vm.totalMovies = data.total_number_of_movies;
        vm.pageSize = data.number_of_movies;
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
