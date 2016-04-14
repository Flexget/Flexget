(function () {
  'use strict';

  angular
    .module('flexget.plugins.movies')
    .component('movieEntry',{
      templateUrl: 'plugins/movies/components/movie-entry/movie-entry.tmpl.html',
      controllerAs: 'vm',
      bindings: {
        movie: '<',
      },
    });
})();
