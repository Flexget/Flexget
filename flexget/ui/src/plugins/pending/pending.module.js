/* global angular, registerPlugin */
(function () {
    'use strict';

    angular
        .module('plugins.pending', [
            'blocks.exception',
            'blocks.router'
        ]);

    registerPlugin('plugins.pending');
}());