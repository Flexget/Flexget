(function () {
	'use strict';

	angular
		.module('plugins.movies')
		.component('movieList', {
			templateUrl: 'plugins/movies/components/movie-list/movie-list.tmpl.html',
			controller: movieListController,
			controllerAs: 'vm',
			bindings: {
				list: '<',
				deleteMovieList: '&',
				tabIndex: '<'
			}
		});


	function movieListController(moviesService, $mdDialog) {
		var vm = this;

		vm.$onInit = activate;
		vm.loadMovies = loadMovies;
		vm.deleteList = deleteList;
		vm.deleteMovie = deleteMovie;
		vm.updateListPage = updateListPage;
		
		var options = {
			page: 1,
			page_size: 10
		}
		
		function activate() {
			//Hack to make the movies from the first tab load (md-on-select not firing for initial tab)
			if (vm.tabIndex == 0) {
				loadMovies();
			}
		}

		function deleteList($event) {
			$event.preventDefault();
			$event.stopPropagation();

			vm.deleteMovieList();
		}

		function loadMovies() {
			moviesService.getListMovies(vm.list.id, options)
				.then(function (data) {
					vm.movies = data.movies;

					vm.currentPage = data.page;
					vm.totalMovies = data.total_number_of_movies;
					vm.pageSize = data.number_of_movies;
				});
		}

		function deleteMovie(list, movie) {
			var confirm = $mdDialog.confirm()
				.title('Confirm deleting movie from list.')
				.htmlContent("Are you sure you want to delete the movie <b>" + movie.title + "</b> from list <b>" + list.name + "?")
				.ok("Forget")
				.cancel("No");

			$mdDialog.show(confirm).then(function () {
				moviesService.deleteMovie(list.id, movie.id)
					.then(function () {
						var index = vm.movies.indexOf(movie);
						vm.movies.splice(index, 1);
					});
			});
		}

		//Call from the pagination to update the page to the selected page
		function updateListPage (index) {
			options.page = index;

			loadMovies();
		}
	}
})();