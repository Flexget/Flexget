(function () {
    'use strict';

    angular.module('flexget.components')
        .directive('toolBar', toolbarDirective);

    function toolbarDirective(toolBar) {
        return {
            restrict: 'E',
            replace: 'true',
            templateUrl: 'components/toolbar/toolbar.tmpl.html',
            link: function (scope, element, attrs) {
                scope.toolBarItems = toolBar.items;
            }
        };
    }

})();