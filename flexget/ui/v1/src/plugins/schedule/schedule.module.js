/* global angular, registerPlugin */
(function () {
    'use strict';

    angular
        .module('plugins.schedule', [
            'blocks.exception',
            'blocks.router'
            //'schemaForm'
        ]);

    registerPlugin('plugins.schedule');
}());