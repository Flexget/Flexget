(function () {
    'use strict';

    angular
    .module('flexget.plugins.series')
    .component('episodeReleases', {
        templateUrl: 'plugins/series/components/episode-releases/episode-releases.tmpl.html',
        controllerAs: 'vm',
        controller: episodesReleasesController,
        bindings: {
            show: '<',
            episode: '<',
            releases: '<'
        },
    });


    function episodesReleasesController($http, $filter) {
        var vm = this;
        //Call from a release item, to reset the release
        vm.resetRelease = function(id) {
            $http.put('/api/series/' + vm.show.show_id + '/episodes/' + vm.episode.episode_id + '/releases/' + id + '/')
            .success(function(data) {
                //Find all downloaded releases, and set their download status to false, which will make the downloaded icon disappear
                $filter('filter')(vm.releases, { release_id: id})[0].release_downloaded = false;
            }).error(function(error) {
                console.log(error);
            });
        }

        //Call from a release item, to forget the release
        vm.forgetRelease = function(release) {
            $http.delete('/api/series/' + vm.show.show_id + '/episodes/' + vm.episode.episode_id + '/releases/' + release.release_id + '/', { params: { forget: true }})
            .success(function(data) {
                //Find index of the release and remove it from the list
                var index = vm.releases.indexOf(release);
                vm.releases.splice(index, 1);

                //Set vars for the accordion
                vm.episode.episode_number_of_releases -= 1;
                if(vm.releases.length == 0) {
                    releasesOpen = false;
                    vm.releases = undefined;
                }

            }).error(function(error) {
                console.log(error);
            });
        }
    }
})();
