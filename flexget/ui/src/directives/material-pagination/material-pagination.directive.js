(function() {
  'use strict';

  angular
    .module('flexget.directives')
    .directive('fgMaterialPagination', fgMaterialPagination);

  /**
   * @ngInject
   */
  function fgMaterialPagination() {
    var directive = {
      restrict: 'E',
      controller: 'materialPaginationController',
      controllerAs: 'vm',
      scope: {
        totalPages: '=',
        gotoPage: '&',
        step: '=',
        currentPage: '='
      },
      templateUrl: 'directives/material-pagination/material-pagination.tmpl.html'
    }
    return directive;
  }

})();