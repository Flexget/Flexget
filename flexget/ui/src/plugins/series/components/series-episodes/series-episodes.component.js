(function () {
    'use strict';

    angular
		.module('plugins.series')
		.component('seriesEpisodesView', {
			templateUrl: 'plugins/series/components/series-episodes/series-episodes.tmpl.html',
			controllerAs: 'vm',
			controller: episodesController,
			bindings: {
				show: '<'
			},
			transclude: true
		});

    function episodesController($http, $mdDialog, seriesService) {
        var vm = this;

		vm.$onInit = activate;
		vm.deleteEpisode = deleteEpisode;

        var options = {
            page: 1,
            page_size: 10
        }

		var params = {
			forget: true
		};

		function activate() {
			getEpisodesList();
		}
		
        //Call from the pagination directive, which triggers other episodes to load
        vm.updateListPage = function (index) {
            options.page = index;

            getEpisodesList();
        }

        //Cal the episodes based on the options
        function getEpisodesList() {
            seriesService.getEpisodes(vm.show, options)
				.then(function (data) {
					//Set the episodes in the vm scope to the loaded episodes
					vm.episodes = data.episodes;


					//set vars for the pagination
					vm.currentPage = data.page;
					vm.totalEpisodes = data.total_number_of_episodes;
					vm.pageSize = options.page_size;

				});
        }

        //action called from the series-episode component
        function deleteEpisode(episode) {
            var confirm = $mdDialog.confirm()
				.title('Confirm forgetting episode.')
				.htmlContent("Are you sure you want to forget episode <b>" + episode.episode_identifier + "</b> from show <b>" + vm.show.show_name + "</b>?<br /> This also removes all downloaded releases for this episode!")
				.ok("Forget")
				.cancel("No");

            $mdDialog.show(confirm).then(function () {
                seriesService.deleteEpisode(vm.show, episode, params)
					.then(function () {
						//Find the index of the episode in the data
						var index = vm.episodes.indexOf(episode);
						//Remove the episode from the list, based on the index
						vm.episodes.splice(index, 1);
					});
            });
        }
    }
}());