(function () {
  'use strict';

  angular.module('flexget.components').directive('sideNav', function (sideNav) {

    return {
      restrict: 'E',
      replace: 'true',
      templateUrl: 'components/sidenav/sidenav.tmpl.html',
      link: function (scope, element, attrs) {
        scope.navItems = sideNav.items;
      }
    };
  });

})();