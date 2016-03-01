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
    scope.$watch('page', function(newValue, oldValue) {
      if(newValue && newValue != oldValue) {
        updateButtons(scope, attributes);
      }
    })
  }

  function addRange(start, end, scope) {
    var i = 0;
    for(i = start; i <= end; i++) {
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

  function updateButtons(scope) {
    var pageCount = Math.ceil(scope.total / scope.pageSize);

    scope.stepList = [];

    var cutOff = 5;

    if(pageCount <= cutOff) {
      addRange(1, pageCount, scope);
    } else {
      // Check if page is in the first 3
      // Then we don't have to shift the numbers left, otherwise we get 0 and -1 values
      if(scope.page - 2 < 2) {
        addRange(1, 5, scope);

      // Check if page is in the last 3
      // Then we don't have to shift the numbers right, otherwise we get higher values without any results
      } else if(scope.page + 2 > pageCount) {
        addRange(pageCount - 4, pageCount, scope);

      // If page is not in the start of end
      // Then we add 2 numbers to each side of the current page
      } else {
        addRange(scope.page - 2, scope.page + 2, scope);
      }
    }
  }

})();