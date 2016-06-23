(function () {
    'use strict';

    angular
		.module('plugins.series')
		.component('seriesEpisode', {
			templateUrl: 'plugins/series/components/series-episode/series-episode.tmpl.html',
			controllerAs: 'vm',
			controller: seriesEpisodeController,
			bindings: {
				episode: '<',
				show: '<',
				deleteEpisode: '&'
			}
		});

    function seriesEpisodeController($mdDialog, $http, seriesService) {
        var vm = this;

		vm.showReleases = showReleases;
		vm.resetReleases = resetReleases;
		vm.deleteReleases = deleteReleases;

		var params = {
			forget: true
		}

		var dialog = {
			template: '<episode-releases show="vm.show" episode="vm.episode"></episode-releases>',
			bindToController: true,
			locals: {
				show: vm.show,
				episode: vm.episode
			},
			controllerAs: 'vm',
			controller: function () { }
		}

        function showReleases() {
			$mdDialog.show(dialog);
        }

		//action called from the series-episode components
        function resetReleases() {
            var confirm = $mdDialog.confirm()
				.title('Confirm resetting releases.')
				.htmlContent("Are you sure you want to reset downloaded releases for <b>" + vm.episode.episode_identifier + "</b> from show <b>" + vm.show.show_name + "</b>?<br /> This does not remove seen entries but will clear the quality to be downloaded again.")
				.ok("Forget")
				.cancel("No");

            $mdDialog.show(confirm).then(function () {
                seriesService.resetReleases(vm.show, vm.episode);
            });
        }

        //Call from the page, to delete all releases
		function deleteReleases() {
            var confirm = $mdDialog.confirm()
				.title('Confirm deleting releases.')
				.htmlContent("Are you sure you want to delete all releases for <b>" + vm.episode.episode_identifier + "</b> from show <b>" + vm.show.show_name + "</b>?<br /> This also removes all seen releases for this episode!")
				.ok("Forget")
				.cancel("No");

            $mdDialog.show(confirm).then(function () {
				seriesService.deleteReleases(vm.show, vm.episode, params)
					.then(function () {
						vm.episode.episode_number_of_releases = 0;
					});
            });
        }
    }
})();