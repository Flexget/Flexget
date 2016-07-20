(function () {
	'use strict';

	angular
		.module('plugins.movies')
		.component('movieEntry', {
			templateUrl: 'plugins/movies/components/movie-entry/movie-entry.tmpl.html',
			controller: movieEntryController,
			controllerAs: 'vm',
			bindings: {
				movie: '<',
				deleteMovie: '&'
			}
		});

	function movieEntryController(moviesService) {
		var vm = this;

		vm.$onInit = activate;
		
		function activate() {
			getMetadata();
		}

		function getMetadata() {
			var params = {
				year: vm.movie.year
			};

			vm.movie.movies_list_ids.forEach(function (id) {
				var newid = {};
				newid[id.id_name] = id.id_value;
				params = angular.extend(params, newid);
			});

			moviesService.getMovieMetadata(vm.movie.title, params).then(function (data) {
				vm.metadata = data;
			});
		}
	}
}());