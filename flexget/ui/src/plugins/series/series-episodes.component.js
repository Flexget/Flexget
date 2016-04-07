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

    //Call from the pagination directive, which triggers other episodes to load
    vm.updateListPage = function(index) {
      options.page = index;

      getEpisodesList();
    }

    vm.goBack = function() {
      $state.go('flexget.series');
    }

    //Cal the episodes based on the options, id is loaded from the route
    function getEpisodesList() {
      $http.get('/api/series/' + $stateParams.id + '/episodes', { params: options })
      .success(function(data) {
        //Set the episodes in the vm scope to the loaded episodes
        vm.episodes = data.episodes;

        //set vars for the pagination
        vm.currentPage = data.page;
        vm.totalEpisodes = data.total_number_of_episodes;
        vm.pageSize = options.page_size;

        // Set show variable to use in dialog boxes and the general header
        vm.show = data.show;
        show = data.show;
      })
      .error(function(error) {
        //TODO: Error handling
        console.log(error);
      });
    }

    //Load initial episodes
    getEpisodesList();

    //action called from the series-episode component
    vm.deleteEpisode = function(episode) {
      var confirm = $mdDialog.confirm()
        .title('Confirm forgetting episode.')
        .htmlContent("Are you sure you want to forget episode <b>" + episode.episode_identifier + "</b> from show " + show + "?<br /> This also removes all downloaded releases for this episode!")
        .ok("Forget")
        .cancel("No");

      $mdDialog.show(confirm).then(function() {
        $http.delete('/api/series/' + $stateParams.id + '/episodes/' + episode.episode_id, { params: { forget: true} })
          .success(function(data) {
            //Find the index of the episode in the data
            var index = vm.episodes.indexOf(episode);
            //Remove the episode from the list, based on the index
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

    //action called from the series-episode components
    vm.resetReleases = function(episode) {
      var confirm = $mdDialog.confirm()
        .title('Confirm resetting releases.')
        .htmlContent("Are you sure you want to reset downloaded releases for <b>" + episode.episode_identifier + "</b> from show " + show + "?<br /> This does not remove seen entries but will clear the quality to be downloaded again.")
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
              .htmlContent("Oops, something went wrong when trying to reset downloaded releases for <b>" + episode.episode_identifier + "</b> from show " + show + ":<br />" + error.message)
              .ok("Ok");

            $mdDialog.show(errorDialog);
          });
      });
    }
  }

})();
