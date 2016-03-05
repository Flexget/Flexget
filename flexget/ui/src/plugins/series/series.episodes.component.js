(function () {
  'use strict';

  angular
    .module('flexget.plugins.series')
    .component('seriesEpisodesView', {
      templateUrl: 'plugins/series/series.episodes.tmpl.html',
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
      $http.get('/api/series/' + $stateParams.id + '/episodes', { params: options, cache: true})
      .success(function(data) {
        vm.episodes = data.episodes;

        vm.currentPage = data.page;
        vm.totalEpisodes = data.total_number_of_episodes;
        vm.pageSize = options.page_size;

        show = data.show;
        loadReleases();
      })
      .error(function(error) {
        console.log(error);
      });
    }

    getEpisodesList();

    vm.forgetEpisode = function(episode) {
      var confirm = $mdDialog.confirm()
      .title('Confirm forgetting episode.')
      .htmlContent("Are you sure you want to forget episode <b>" + episode.episode_identifier + "</b> from show " + show + "?")
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
        })
      });
    }

    function loadReleases() {
      var params = {
        downloaded: 'downloaded'
      }
      vm.episodes.map(function(episode) {
        $http.get('/api/series/' + $stateParams.id + '/episodes/' + episode.episode_id + '/releases', { params: params })
        .success(function(data) {
          episode.releases = data.releases;
        })
        .error(function(error) {
          console.log(error);
        })
      })
    }
  }

})();
