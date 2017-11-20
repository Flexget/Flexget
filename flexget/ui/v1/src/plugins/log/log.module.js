/* global angular, registerPlugin */
(function () {
    'use strict';

    angular
        .module('plugins.log', [
            'blocks.exception',
            'blocks.router',

            'components.toolbar',
            'ui.grid',
            'ui.grid.autoResize',
            'ui.grid.autoScroll'
        ]);

    registerPlugin('plugins.log');
}());