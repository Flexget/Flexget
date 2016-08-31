/* global angular, registerPlugin */
(function () {
    'use strict';

    angular
        .module('plugins.history', [
            'angular-cache',
            'angular.filter',

            'blocks.exception',
            'blocks.router'
        ]);

    registerPlugin('plugins.history');
}());