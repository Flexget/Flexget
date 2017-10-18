/* global angular, registerPlugin */
(function () {
    'use strict';

    angular
        .module('plugins.status', [
            'blocks.exception',
            'blocks.router',
            'mdDataTable'
        ]);

    registerPlugin('plugins.status');
}());