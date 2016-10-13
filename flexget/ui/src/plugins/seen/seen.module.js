/* global angular, registerPlugin */
(function () {
    'use strict';

    angular
        .module('plugins.seen', [
            'http-etag',
            
            'blocks.pagination',
            'blocks.exception',
            'blocks.router'
        ]);

    registerPlugin('plugins.seen');
}());