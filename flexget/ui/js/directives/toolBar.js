(function () {
  'use strict';

  angular.module('flexget').directive('toolBar', function (toolBar) {

    var template = '<div class="admin-toolbar">' +
        '<md-toolbar class="admin-toolbar">' +
            '<div class="md-toolbar-tools">' +
                '<md-button class="md-icon-button" ng-click="toggleNav()" style="width: 40px">' +
                    '<md-icon class="fa fa-bars" aria-label="Menu"></md-icon>' +
                '</md-button>' +
                '<span flex></span>' +
                '<md-button ng-repeat="item in toolBarItem" ng-click="item.action()" aria-label="{{ item.label }}">' +
                    '<md-icon class="{{ item.cssClass }}"></md-icon>' +
                '</md-button>' +
                '<md-menu md-offset="0 -7">' +
                    '<md-button aria-label="Open demo menu" class="md-icon-button" ng-click="$mdOpenMenu($event)">' +
                        '<md-icon md-menu-origin md-svg-icon="call:chat"></md-icon>' +
                    '</md-button>' +
                    '<md-menu-content width="2">' +
                        '<md-menu-item ng-repeat="item in [1, 2, 3]">' +
                            '<md-button ng-click="ctrl.announceClick($index)"> <span md-menu-align-target>Option</span> {{item}} </md-button>' +
                        '</md-menu-item>' +
                    '</md-menu-content>' +
                '</md-menu>' +
            '</div>' +
        '</md-toolbar>' +
    '</div>'

    return {
      restrict: 'E',
      replace: 'true',
      template: template,
      link: function (scope, element, attrs) {
        scope.toolBarItem = toolBar.items;
      }
    };
  });

})();