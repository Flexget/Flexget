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
        show: '<',
        deleteEpisode: '&',
        resetReleases: '&'
      },
    });

    function seriesEpisodeController($mdDialog, $http, $stateParams, $filter){
      var vm = this;

      //Small hacks to make the accordion work, if that ever gets in Angular Material, this can be replaced
      var releasesOpen = false;
      vm.toggleReleases = function() {
        releasesOpen = !releasesOpen;

        if(releasesOpen && !vm.releases)
        {
          //If the accordion is open and no releases are loaded yet, then load them
          loadReleases();
        }
      }

      vm.isOpen = function() {
        return releasesOpen;
      }

      //Call from the page, to delete all releases
      vm.deleteReleases = function() {
        var confirm = $mdDialog.confirm()
          .title('Confirm deleting releases.')
          .htmlContent("Are you sure you want to delete all releases for <b>" + vm.episode.episode_identifier + "</b> from show " + vm.show + "?<br /> This also removes all seen releases for this episode!")
          .ok("Forget")
          .cancel("No");

        $mdDialog.show(confirm).then(function() {
          $http.delete('/api/series/' + $stateParams.id + '/episodes/' + vm.episode.episode_id + '/releases', { params: { forget: true}})
            .success(function(data) {
              //Remove all loaded releases from the page and set variables for the accordion
              vm.releases = undefined;
              vm.episode.episode_number_of_releases = 0;
              releasesOpen = false;
            })
            .error(function(error) {
              var errorDialog = $mdDialog.alert()
                .title("Something went wrong")
                .htmlContent("Oops, something went wrong when trying to forget <b>" + vm.episode.episode_identifier + "</b> from show " + vm.show + ":<br />" + error.message)
                .ok("Ok");

              $mdDialog.show(errorDialog);
            });
        });
      }

      //Load the releases upon opening the accordion
      function loadReleases() {
        $http.get('/api/series/' + $stateParams.id + '/episodes/' + vm.episode.episode_id + '/releases')
        .success(function(data) {
          vm.releases = data.releases;
        }).error(function(error) {
          console.log(error);
        });
      }

      //Call from a release item, to reset the release
      vm.resetRelease = function(id) {
        $http.put('/api/series/' + $stateParams.id + '/episodes/' + vm.episode.episode_id + '/releases/' + id + '/')
          .success(function(data) {
            //Find all downloaded releases, and set their download status to false, which will make the downloaded icon disappear
            $filter('filter')(vm.releases, { release_id: id})[0].release_downloaded = false;
          }).error(function(error) {
            console.log(error);
          });
      }

      //Call from a release item, to forget the release
      vm.forgetRelease = function(release) {
        $http.delete('/api/series/' + $stateParams.id + '/episodes/' + vm.episode.episode_id + '/releases/' + release.release_id + '/', { params: { forget: true }})
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
