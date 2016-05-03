(function () {
  'use strict';
  angular
  .module("flexget.plugins.movies")
  .component('moviesView', {
    templateUrl: 'plugins/movies/movies.tmpl.html',
    controllerAs: 'vm',
    controller: moviesController,
  });

  function moviesController($http, $mdDialog, $scope, moviesService) {
    var vm = this;

    var options = {
      page: 1,
      page_size: 10
    }

    moviesService.getLists().then(function(data)  {
      vm.lists = data.movie_lists;
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

      moviesService.getListMovies(listId, options)
        .then(function(data) {
          vm.movies = data.movies;

          vm.currentPage = data.page;
          vm.totalMovies = data.total_number_of_movies;
          vm.pageSize = data.number_of_movies;
        });
    }


    vm.deleteMovie = function(list, movie) {
      var confirm = $mdDialog.confirm()
      .title('Confirm deleting movie from list.')
      .htmlContent("Are you sure you want to delete the movie <b>" + movie.title + "</b> from list <b>" + list.name + "?")
      .ok("Forget")
      .cancel("No");

      $mdDialog.show(confirm).then(function() {
        moviesService.deleteMovie(list.id, movie.id)
          .then(function() {
            var index = vm.movies.indexOf(movie);
            vm.movies.splice(index, 1);
          });
      });
    }

    vm.deleteList = function(list) {
      var confirm = $mdDialog.confirm()
      .title('Confirm deleting movie list.')
      .htmlContent("Are you sure you want to delete the movie list <b>" + list.name + "</b>?")
      .ok("Forget")
      .cancel("No");

      //Actually show the confirmation dialog and place a call to DELETE when confirmed
      $mdDialog.show(confirm).then(function() {
       moviesService.deleteList(list.id)
          .then(function() {
            var index = vm.lists.indexOf(list);
            vm.lists.splice(index, 1);
          });
      });
    }
  }
})();
