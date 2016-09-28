/* global angular, registerPlugin */
(function () {
    'use strict';

    angular
        .module('plugins.seen', [
            'http-etag',

            'blocks.exception',
            'blocks.router'
        ]);

    registerPlugin('plugins.seen');
}());