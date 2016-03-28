(function () {
  'use strict';

  angular
    .module('flexget.plugins.series')
    .component('seriesEpisodesView', {
      templateUrl: 'plugins/series/series-episodes.tmpl.html',
      controllerAs: 'vm',
      controller: episodesController,
    });

  function episodesController($http, $stateParams, $mdDialog, $state) {
    var vm = this;

    var show = "";

    var options = {
      page: 1,
      page_size: 10
    }

    vm.updateListPage = function(index) {
      options.page = index;

      getEpisodesList();
    }

    vm.goBack = function() {
      $state.go('flexget.series');
    }

    function getEpisodesList() {
      $http.get('/api/series/' + $stateParams.id + '/episodes', { params: options })
      .success(function(data) {
        vm.episodes = data.episodes;
        vm.currentPage = data.page;
        vm.totalEpisodes = data.total_number_of_episodes;
        vm.pageSize = options.page_size;

        vm.show = data.show;

        show = data.show;
      })
      .error(function(error) {
        console.log(error);
      });
    }

    getEpisodesList();

    vm.deleteEpisode = function(episode) {
      var confirm = $mdDialog.confirm()
        .title('Confirm forgetting episode.')
        .htmlContent("Are you sure you want to forget episode <b>" + episode.episode_identifier + "</b> from show " + show + "?\n This also removes all seen entries for this episode!")
        .ok("Forget")
        .cancel("No");

      $mdDialog.show(confirm).then(function() {
        $http.delete('/api/series/' + $stateParams.id + '/episodes/' + episode.episode_id)
          .success(function(data) {
            var index = vm.episodes.indexOf(episode);
            vm.episodes.splice(index, 1);
          })
          .error(function(error) {
            var errorDialog = $mdDialog.alert()
              .title("Something went wrong")
              .htmlContent("Oops, something went wrong when trying to forget <b>" + episode.episode_identifier + "</b> from show " + show + ":\n" + error.message)
              .ok("Ok");

            $mdDialog.show(errorDialog);
          });
      });
    }

    vm.deleteReleases = function(episode) {
      var confirm = $mdDialog.confirm()
        .title('Confirm deleting releases.')
        .htmlContent("Are you sure you want to delete all releases for <b>" + episode.episode_identifier + "</b> from show " + show + "?\n This also removes all seen releases for this episode!")
        .ok("Forget")
        .cancel("No");

      $mdDialog.show(confirm).then(function() {
        $http.delete('/api/series/' + $stateParams.id + '/episodes/' + episode.episode_id + '/releases', { params: { delete_seen: true}})
          .success(function(data) {
            //TODO: Check what to do, prob remove all release if any loaded
          })
          .error(function(error) {
            var errorDialog = $mdDialog.alert()
              .title("Something went wrong")
              .htmlContent("Oops, something went wrong when trying to forget <b>" + episode.episode_identifier + "</b> from show " + show + ":\n" + error.message)
              .ok("Ok");

            $mdDialog.show(errorDialog);
          });
      });
    }

    vm.resetReleases = function(episode) {
      var confirm = $mdDialog.confirm()
        .title('Confirm resetting releases.')
        .htmlContent("Are you sure you want to reset downloaded releases for <b>" + episode.episode_identifier + "</b> from show " + show + "?\n This does not remove seen entries but will clear the quality to be downloaded again.")
        .ok("Forget")
        .cancel("No");

      $mdDialog.show(confirm).then(function() {
        $http.put('/api/series/' + $stateParams.id + '/episodes/' + episode.episode_id + '/releases')
          .success(function(data) {
            //TODO: Handle reset releases, remove them from view if they are showm
          })
          .error(function(error) {
            var errorDialog = $mdDialog.alert()
              .title("Something went wrong")
              .htmlContent("Oops, something went wrong when trying to reset downloaded releases for <b>" + episode.episode_identifier + "</b> from show " + show + ":\n" + error.message)
              .ok("Ok");

            $mdDialog.show(errorDialog);
          });
      });
    }
  }

})();
