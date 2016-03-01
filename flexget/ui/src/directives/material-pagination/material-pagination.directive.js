(function() {
  'use strict';

  angular
    .module('flexget.directives')
    .directive('fgMaterialPagination', fgMaterialPagination);

  /* @ngInject */
  function fgMaterialPagination() {
    var directive = {
      restrict: 'E',
      scope: {
        page: '=',
        pageSize: '=',
        total: '=',
        activeClass: '@',
        pagingAction: '&',
      },
      link: pagingLink,
      templateUrl: 'directives/material-pagination/material-pagination.tmpl.html'
    }
    return directive;
  }

  function pagingLink(scope, element, attributes) {
    scope.$watchCollection('[total, pageSize]', function(newValue, oldValue) {
      if(newValue[0] && newValue[1] && newValue != oldValue) {
        init(scope, attributes);
      }
    })
  }

  function init(scope, attrs) {
    if(!scope.pageSize || scope.pageSize <= 0) {
      scope.pageSize = 1;
    }

    var pageCount = Math.ceil(scope.total / scope.pageSize);

    scope.stepList = [];

    for(var i = 1; i <= pageCount; i++) {
      scope.stepList.push({
        value: i,
        activeClass: scope.activeClass,
        action: function() {
          internalAction(scope, this.value);
        }
      })
    }
  }

  function internalAction(scope, page) {
    if(scope.page == page) {
      return;
    }

    scope.pagingAction({
      index: page
    });
  }

})();