/* global angular, registerPlugin */
(function () {
    'use strict';

    angular
        .module('plugins.history', [
            'angular.filter',

            'blocks.pagination',
            'blocks.exception',
            'blocks.router'
        ]);

    registerPlugin('plugins.history');
}());