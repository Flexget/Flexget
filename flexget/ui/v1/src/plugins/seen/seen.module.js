/* global angular, registerPlugin */
(function () {
    'use strict';

    angular
        .module('plugins.seen', [
            'blocks.pagination',
            'blocks.exception',
            'blocks.router'
        ]);

    registerPlugin('plugins.seen');
}());