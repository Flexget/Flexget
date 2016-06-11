(function () {
    'use strict';

    angular
		.module('plugins.series')
		.component('episodeReleases', {
			templateUrl: 'plugins/series/components/episode-releases/episode-releases.tmpl.html',
			controllerAs: 'vm',
			controller: episodesReleasesController,
			bindings: {
				show: '<',
				episode: '<'
			},
		});

    function episodesReleasesController($http, $filter, $mdDialog, seriesService) {
        var vm = this;

		vm.$onInit = activate;
		vm.cancel = cancel;
		vm.resetRelease = resetRelease;
		vm.forgetRelease = forgetRelease;

		var params = {
			forget: true
		};

		function activate() {
			loadReleases();
		}

        //Call from a release item, to reset the release
        function resetRelease(release) {

            var confirm = $mdDialog.confirm()
				.title('Confirm resetting a release')
				.htmlContent("Are you sure you want to reset the release <b>" + release.release_title + "</b>?")
				.ok("reset")
				.cancel("No");

            $mdDialog.show(confirm).then(function () {
                seriesService.resetRelease(vm.show, vm.episode, release).then(function (data) {
                    //Find all downloaded releases, and set their download status to false, which will make the downloaded icon disappear
                    //$filter('filter')(vm.releases, { release_id: id})[0].release_downloaded = false;
                })
            })

        }

        //Call from a release item, to forget the release
        function forgetRelease(release) {
            var confirm = $mdDialog.confirm()
				.title('Confirm forgetting a release')
				.htmlContent("Are you sure you want to delete the release <b>" + release.release_title + "</b>?")
				.ok("Forget")
				.cancel("No");

            $mdDialog.show(confirm).then(function () {
                seriesService.forgetRelease(vm.show, vm.episode, release, params).then(function (data) {
                    //Find index of the release and remove it from the list
                    var index = vm.releases.indexOf(release);
                    vm.releases.splice(index, 1);

                    vm.episode.episode_number_of_releases -= 1;
                    if (vm.releases.length == 0) {
                        vm.releases = undefined;
                    }
                })
            })
        }

        function loadReleases() {
			seriesService.loadReleases(vm.show, vm.episode).then(function (data) {
				vm.releases = data.releases;
			});
        }

		function cancel() {
			$mdDialog.cancel();
		}
    }
})();										