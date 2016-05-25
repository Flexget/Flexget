(function () {
    'use strict';

    angular.module('flexget.layout')
        .component('toolBar', {
            templateUrl: 'layout/toolbar/toolbar.tmpl.html',
            controllerAs: 'vm',
            controller: toolbarController
        });

    function toolbarController(sideNav, toolBar) {
        var vm = this;
        
        //TODO: move and refactor some stuff around if possible
        vm.toggle = sideNav.toggle;
        vm.toolBarItems = toolBar.items;
    }

})();