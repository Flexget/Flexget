/* global angular registerPlugin */
(function () {
    'use strict';

    angular
        .module('plugins.execute', [
            'angular-cache',
            
            'blocks.exception',
            'blocks.router'
        ]);

    registerPlugin('plugins.execute');
}());