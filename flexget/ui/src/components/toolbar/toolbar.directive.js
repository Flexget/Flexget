(function () {
    'use strict';

    angular.module('flexget.components')
        .directive('toolBar', toolbarDirective);

    function toolbarDirective(toolBar) {
        return {
            restrict: 'E',
            replace: 'true',
            templateUrl: 'components/toolbar/toolbar.tmpl.html',
            controller: function ($scope, sideNav) {
                $scope.toggle = sideNav.toggle;
                $scope.toolBarItems = toolBar.items;
            }
        };
    }

})();