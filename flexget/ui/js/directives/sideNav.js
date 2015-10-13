(function () {
  'use strict';

  angular.module('flexget').directive('sideNav', function (sideNav) {

    var template = '<md-sidenav' +
      ' layout="column" class="nav-menu md-sidenav-left md-sidenav-left md-whiteframe-z2" md-component-id="left" md-is-locked-open="$mdMedia(\'gt-lg\')">' +
      '<md-content layout="column" flex>' +
      '<md-list>' +
      '<md-list-item class="header">Menu</md-list-item>' +
      '<md-list-item ng-repeat="item in navItems">' +
      '<md-button href="{{ item.href }}" ng-click="closeNav()" flex>' +
      '<md-icon class="{{ item.icon }}"></md-icon>' +
      '{{ item.caption }}' +
      '</md-button>' +
      '</md-list-item>' +
      '</md-list>' +
      '</md-content>' +
      '</md-sidenav>';

    return {
      restrict: 'E',
      replace: 'true',
      template: template,
      link: function (scope, element, attrs) {
        scope.navItems = sideNav.items;
      }
    };
  });

})();