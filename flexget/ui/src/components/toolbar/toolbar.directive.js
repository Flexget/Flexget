(function () {
    'use strict';

    angular.module('flexget.components')
        .directive('toolBar', toolbarDirective);

    function toolbarDirective(toolBar) {
        return {
            restrict: 'E',
            replace: 'true',
            templateUrl: 'components/toolbar/toolbar.tmpl.html',
            controllerAs: 'vm',
            controller: function (sideNav) {
                var vm = this;
                vm.toggle = sideNav.toggle;
                vm.toolBarItems = toolBar.items;
            }
        };
    }

})();