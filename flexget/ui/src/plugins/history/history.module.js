/* global angular, registerPlugin */
(function () {
    'use strict';

    angular
        .module('plugins.history', [
            'http-etag',
            'angular.filter',

            'blocks.exception',
            'blocks.router'
        ]);

    registerPlugin('plugins.history');
}());