/* global angular, registerPlugin */
(function () {
    'use strict';

    angular
        .module('plugins.series', [
            'ngMaterial',

            'blocks.pagination',            
            'blocks.exception',
            'blocks.router'
        ]);

    registerPlugin('plugins.series');
}());