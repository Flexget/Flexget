(function () {
  'use strict';

  angular
    .module('flexget.plugins.series')
    .component('seriesEpisode', {
      templateUrl: 'plugins/series/components/series-episode/series-episode.tmpl.html',
      controllerAs: 'vm',
      controller: seriesEpisodeController,
      bindings: {
        episode: '<',
        deleteEpisode: '&',
        deleteReleases: '&',
        resetReleases: '&'
      },
    });

    function seriesEpisodeController($mdDialog, $http, $stateParams, $filter){
      var vm = this;

      var releasesOpen = false;
      vm.toggleReleases = function() {
        releasesOpen = !releasesOpen;

        if(releasesOpen && !vm.releases)
        {
          vm.loadReleases();
        }
      }

      vm.isOpen = function() {
        return releasesOpen;
      }

      vm.loadReleases = function() {
        var params = {
          downloaded: 'all'
        }

        $http.get('/api/series/' + $stateParams.id + '/episodes/' + vm.episode.episode_id + '/releases', { params: params, cache: true})
        .success(function(data) {
          vm.releases = data.releases;
        }).error(function(error) {
          console.log(error);
        });
      }

      vm.resetRelease = function(id) {
        $http.put('/api/series/' + $stateParams.id + '/episodes/' + vm.episode.episode_id + '/releases/' + id + '/')
          .success(function(data) {
            $filter('filter')(vm.releases, { release_id: id})[0].release_downloaded = false;
          }).error(function(error) {
            console.log(error);
          });
      }

      vm.forgetRelease = function(release) {
        $http.delete('/api/series/' + $stateParams.id + '/episodes/' + vm.episode.episode_id + '/releases/' + release.release_id + '/', { params: { delete_seen: true }})
          .success(function(data) {
            var index = vm.releases.indexOf(release);
            vm.releases.splice(index, 1);
            console.log(vm.releases);
          }).error(function(error) {
            console.log(error);
          });
      }
    }
})();
