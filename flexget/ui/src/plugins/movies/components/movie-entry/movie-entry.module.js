(function () {
  'use strict';

  angular
    .module('flexget.plugins.movies')
    .component('movieEntry',{
      templateUrl: 'plugins/movies/components/movie-entry/movie-entry.tmpl.html',
      controller: function() {
        var vm = this;
      },
      controllerAs: 'vm',
      bindings: {
        metadata: '<',
        deleteMovie: '&'
      },
    });
})();
