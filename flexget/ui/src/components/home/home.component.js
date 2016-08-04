/* global angular */
(function () {
    'use strict';

    angular
        .module('components.home')
        .component('home', {
            templateUrl: 'components/home/home.tmpl.html',
            controllerAs: 'vm',
            controller: homeController
        });

    function homeController() {
    }
}());