(function () {
  'use strict';

  angular
    .module('flexget.plugins.series')
    .component('seriesView', {
      templateUrl: 'plugins/series/series.tmpl.html',
      controllerAs: 'vm',
      controller: seriesController,
    });

  function seriesController($http, $mdDialog) {
    var vm = this;

    var options = {
      page: 1,
      page_size: 10,
      in_config: 'all',
      lookup: 'tvmaze'
    }

    vm.searchTerm = "";

    function getSeriesList() {
      $http.get('/api/series/', { params: options, cache: true })
      .success(function(data) {
        vm.series = data.shows;

        //Set vars for pagination
        vm.currentPage = data.page;
        vm.totalShows = data.total_number_of_shows;
        vm.pageSize = data.page_size;
      });
    }

    vm.confirmDelete = function(show) {
      $http.delete('/api/series/' + show.show_id)
        .success(function(data) {
          var index = vm.series.indexOf(show);
          vm.series.splice(index, 1);
        })
        .error(function(error) {
          
        })
    }

    //Call from the pagination to update the page to the selected page
    vm.updateListPage = function(index) {
      options.page = index;

      getSeriesList();
    }

    vm.search = function() {
      $http.get('/api/series/search/' + vm.searchTerm, { params: options })
      .success(function(data) {
        vm.series = data.shows;
      });
    }

    

    //Load initial list of series
    getSeriesList();
  }

})();
